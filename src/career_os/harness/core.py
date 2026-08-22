from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping
from uuid import uuid4


class AgentState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class Event:
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))


class EventLog:
    """Append-only event log; callers receive immutable snapshots."""

    def __init__(self) -> None:
        self._events: list[Event] = []

    def append(self, event: Event) -> None:
        self._events.append(event)

    def snapshot(self) -> tuple[Event, ...]:
        return tuple(self._events)


@dataclass(frozen=True)
class AgentContext:
    objective: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolRequest:
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    risk: str = "low"


@dataclass(frozen=True)
class ToolResult:
    name: str
    success: bool
    output: Any = None
    error: str | None = None


class AgentHarness:
    """Small provider-agnostic reasoning/action boundary.

    The model/planner is injected; the harness owns state, events and policy.
    This keeps provider-specific behavior out of Career OS business logic.
    """

    def __init__(self, context: AgentContext, policy: Any, planner: Callable[[AgentContext, tuple[Event, ...]], ToolRequest | None]) -> None:
        self.context = context
        self.policy = policy
        self.planner = planner
        self.state = AgentState.IDLE
        self.events = EventLog()
        self.pending: ToolRequest | None = None

    def step(self) -> ToolRequest | None:
        if self.state in {AgentState.COMPLETED, AgentState.FAILED}:
            return None
        self.state = AgentState.RUNNING
        request = self.planner(self.context, self.events.snapshot())
        if request is None:
            self.state = AgentState.COMPLETED
            self.events.append(Event("run.completed"))
            return None
        self.events.append(Event("tool.requested", {"name": request.name, "arguments": dict(request.arguments)}))
        if self.policy.requires_approval(request):
            self.pending = request
            self.state = AgentState.WAITING_APPROVAL
            self.events.append(Event("approval.required", {"tool": request.name}))
            return request
        return request

    def approve(self) -> ToolRequest:
        if self.state != AgentState.WAITING_APPROVAL or self.pending is None:
            raise RuntimeError("no pending approval")
        request = self.pending
        self.pending = None
        self.state = AgentState.RUNNING
        self.events.append(Event("approval.granted", {"tool": request.name}))
        return request

    def reject(self) -> None:
        if self.state != AgentState.WAITING_APPROVAL or self.pending is None:
            raise RuntimeError("no pending approval")
        name = self.pending.name
        self.pending = None
        self.state = AgentState.FAILED
        self.events.append(Event("approval.rejected", {"tool": name}))
