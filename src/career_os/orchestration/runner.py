from __future__ import annotations

from typing import Any

from career_os.orchestration.repository import WorkflowRepository
from career_os.orchestration.workflow import WorkflowNode, WorkflowOrchestrator, WorkflowState


class DurableWorkflowRunner:
    """Persist workflow state after every externally visible advancement."""

    def __init__(self, nodes: list[WorkflowNode], repository: WorkflowRepository) -> None:
        self.workflow = WorkflowOrchestrator(nodes)
        self.repository = repository

    def start(self, run_id: str, *, context: dict[str, Any] | None = None) -> WorkflowState:
        if self.repository.get(run_id) is not None:
            raise ValueError(f"workflow run already exists: {run_id}")
        state = self.workflow.start(run_id, context=context)
        self.repository.save(state)
        return self.advance(run_id)

    def advance(
        self,
        run_id: str,
        *,
        approval: bool | None = None,
        input_value: Any = None,
    ) -> WorkflowState:
        state = self.repository.get(run_id)
        if state is None:
            raise KeyError(f"unknown workflow run: {run_id}")
        updated = self.workflow.run(state, approval=approval, input_value=input_value)
        self.repository.save(updated)
        return updated
