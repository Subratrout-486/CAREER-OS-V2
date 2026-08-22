from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from career_os.orchestration.workflow import WorkflowState


class WorkflowRepository(Protocol):
    """Persistence boundary for resumable workflow state."""

    def save(self, state: WorkflowState) -> None: ...

    def get(self, run_id: str) -> WorkflowState | None: ...


class InMemoryWorkflowRepository:
    """Reference repository for local development and deterministic tests.

    A real deployment can replace this with Postgres/Redis without changing the
    orchestration state machine or specialist agents.
    """

    def __init__(self) -> None:
        self._states: dict[str, WorkflowState] = {}

    def save(self, state: WorkflowState) -> None:
        self._states[state.run_id] = deepcopy(state)

    def get(self, run_id: str) -> WorkflowState | None:
        state = self._states.get(run_id)
        return deepcopy(state) if state is not None else None
