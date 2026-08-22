from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_INPUT = "waiting_input"
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
    resume_node: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    events: list[AuditEvent] = field(default_factory=list)
    attempts: dict[str, int] = field(default_factory=dict)
    approved_nodes: set[str] = field(default_factory=set)
    approval_node: str | None = None
    input_node: str | None = None
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
    remain responsible for domain work. State is explicit and serializable so a
    later durable repository (for example Postgres) can resume a run safely.
    """

    def __init__(self, nodes: list[WorkflowNode]) -> None:
        if not nodes:
            raise ValueError("At least one workflow node is required")
        if any(node.max_attempts < 1 for node in nodes):
            raise ValueError("max_attempts must be at least 1")
        self._nodes = {node.name: node for node in nodes}
        if len(self._nodes) != len(nodes):
            raise ValueError("Workflow node names must be unique")
        self._order = [node.name for node in nodes]

    def start(self, run_id: str, *, context: dict[str, Any] | None = None) -> WorkflowState:
        return WorkflowState(run_id=run_id, context=dict(context or {}))

    def run(
        self,
        state: WorkflowState,
        *,
        approval: bool | None = None,
        input_value: Any = None,
    ) -> WorkflowState:
        """Advance a run until it completes, fails, or reaches an external gate."""
        if state.status in (RunStatus.COMPLETED, RunStatus.FAILED):
            return state

        if state.status is RunStatus.WAITING_APPROVAL:
            if approval is None:
                return state
            node_name = state.approval_node
            if approval is False:
                state.status = RunStatus.FAILED
                state.error = "Human approval rejected"
                state.events.append(
                    AuditEvent(node_name or "workflow", NodeOutcome.FAIL, state.error)
                )
                return state
            if node_name:
                state.approved_nodes.add(node_name)
            state.approval_node = None
            state.resume_node = node_name
            state.status = RunStatus.RUNNING

        if state.status is RunStatus.WAITING_INPUT:
            if input_value is None:
                return state
            node_name = state.input_node
            if node_name:
                state.context[f"input:{node_name}"] = input_value
            state.input_node = None
            state.resume_node = node_name
            state.status = RunStatus.RUNNING

        if state.status is RunStatus.PENDING:
            state.status = RunStatus.RUNNING

        start_index = self._next_index(state)
        state.resume_node = None
        for index in range(start_index, len(self._order)):
            node = self._nodes[self._order[index]]
            state.current_node = node.name

            if node.requires_approval and node.name not in state.approved_nodes:
                state.approval_node = node.name
                state.status = RunStatus.WAITING_APPROVAL
                state.events.append(
                    AuditEvent(node.name, NodeOutcome.AWAIT_APPROVAL, "Human approval required")
                )
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
                state.approval_node = node.name
                state.resume_node = node.name
                state.status = RunStatus.WAITING_APPROVAL
                return state
            if outcome is NodeOutcome.AWAIT_INPUT:
                state.input_node = node.name
                state.resume_node = node.name
                state.status = RunStatus.WAITING_INPUT
                return state
            if outcome is NodeOutcome.RETRY:
                if attempt < node.max_attempts:
                    continue
                state.status = RunStatus.FAILED
                state.error = f"Node {node.name} exhausted retries"
                state.events.append(AuditEvent(node.name, NodeOutcome.FAIL, state.error))
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

    def _next_index(self, state: WorkflowState) -> int:
        node = state.resume_node or state.current_node
        if node is None:
            return 0
        index = self._order.index(node)
        return index if state.resume_node else index + 1
