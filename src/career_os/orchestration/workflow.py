from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class NodeOutcome(StrEnum):
    NEXT = "next"
    COMPLETE = "complete"
    AWAIT_APPROVAL = "await_approval"
    AWAIT_INPUT = "await_input"
    RETRY = "retry"
    FAIL = "fail"


@dataclass(frozen=True)
class AuditEvent:
    node: str
    outcome: NodeOutcome
    message: str = ""


@dataclass
class WorkflowState:
    run_id: str
    status: RunStatus = RunStatus.PENDING
    current_node: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    events: list[AuditEvent] = field(default_factory=list)
    attempts: dict[str, int] = field(default_factory=dict)
    approved: bool = False
    error: str | None = None


@dataclass(frozen=True)
class WorkflowNode:
    name: str
    handler: Callable[[WorkflowState], NodeOutcome]
    max_attempts: int = 1
    requires_approval: bool = False


class WorkflowOrchestrator:
    """Dependency-light, deterministic orchestration for Career OS workflows.

    The orchestrator owns state transitions and audit events; specialist agents
    remain responsible for domain work. No model or provider dependency is needed.
    """

    def __init__(self, nodes: list[WorkflowNode]) -> None:
        if not nodes:
            raise ValueError("At least one workflow node is required")
        self._nodes = {node.name: node for node in nodes}
        if len(self._nodes) != len(nodes):
            raise ValueError("Workflow node names must be unique")
        self._order = [node.name for node in nodes]

    def start(self, run_id: str, *, context: dict[str, Any] | None = None) -> WorkflowState:
        return WorkflowState(run_id=run_id, context=dict(context or {}))

    def run(self, state: WorkflowState, *, approval: bool | None = None) -> WorkflowState:
        if state.status is RunStatus.COMPLETED:
            return state  # idempotent replay
        if state.status is RunStatus.FAILED:
            return state

        if state.status is RunStatus.WAITING_APPROVAL:
            if approval is None:
                return state
            if not approval:
                state.status = RunStatus.FAILED
                state.error = "Human approval rejected"
                return state
            state.approved = True
            state.status = RunStatus.RUNNING

        if state.status is RunStatus.PENDING:
            state.status = RunStatus.RUNNING

        start_index = self._order.index(state.current_node) if state.current_node in self._nodes else 0
        if state.current_node is not None and state.status is RunStatus.RUNNING:
            start_index += 1

        for index in range(start_index, len(self._order)):
            node = self._nodes[self._order[index]]
            state.current_node = node.name
            if node.requires_approval and not state.approved:
                state.status = RunStatus.WAITING_APPROVAL
                state.events.append(AuditEvent(node.name, NodeOutcome.AWAIT_APPROVAL, "Human approval required"))
                return state

            attempt = state.attempts.get(node.name, 0) + 1
            state.attempts[node.name] = attempt
            try:
                outcome = node.handler(state)
            except Exception as exc:  # workflow boundary: preserve failure in state
                outcome = NodeOutcome.FAIL
                state.error = str(exc)

            state.events.append(AuditEvent(node.name, outcome, state.error or ""))
            if outcome is NodeOutcome.AWAIT_APPROVAL:
                state.status = RunStatus.WAITING_APPROVAL
                return state
            if outcome is NodeOutcome.AWAIT_INPUT:
                state.status = RunStatus.WAITING_APPROVAL
                return state
            if outcome is NodeOutcome.RETRY:
                if attempt < node.max_attempts:
                    return self.run(state)
                state.status = RunStatus.FAILED
                state.error = state.error or f"Node {node.name} exhausted retries"
                return state
            if outcome is NodeOutcome.FAIL:
                state.status = RunStatus.FAILED
                state.error = state.error or f"Node {node.name} failed"
                return state
            if outcome is NodeOutcome.COMPLETE:
                state.status = RunStatus.COMPLETED
                return state

        state.status = RunStatus.COMPLETED
        return state
