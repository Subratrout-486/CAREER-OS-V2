import pytest

from career_os.orchestration.repository import InMemoryWorkflowRepository
from career_os.orchestration.runner import DurableWorkflowRunner
from career_os.orchestration.workflow import NodeOutcome, RunStatus, WorkflowNode


def test_runner_persists_approval_pause_and_resume() -> None:
    calls: list[str] = []
    runner = DurableWorkflowRunner(
        [
            WorkflowNode("prepare", lambda _: calls.append("prepare") or NodeOutcome.NEXT),
            WorkflowNode("submit", lambda _: calls.append("submit") or NodeOutcome.COMPLETE, requires_approval=True),
        ],
        InMemoryWorkflowRepository(),
    )

    state = runner.start("run-1")
    assert state.status is RunStatus.WAITING_APPROVAL
    assert calls == ["prepare"]

    state = runner.advance("run-1")
    assert state.status is RunStatus.WAITING_APPROVAL
    assert calls == ["prepare"]

    state = runner.advance("run-1", approval=True)
    assert state.status is RunStatus.COMPLETED
    assert calls == ["prepare", "submit"]


def test_runner_rejects_duplicate_run_ids() -> None:
    runner = DurableWorkflowRunner(
        [WorkflowNode("finish", lambda _: NodeOutcome.COMPLETE)],
        InMemoryWorkflowRepository(),
    )
    runner.start("run-duplicate")
    with pytest.raises(ValueError, match="already exists"):
        runner.start("run-duplicate")


def test_runner_requires_known_run() -> None:
    runner = DurableWorkflowRunner(
        [WorkflowNode("finish", lambda _: NodeOutcome.COMPLETE)],
        InMemoryWorkflowRepository(),
    )
    with pytest.raises(KeyError, match="unknown workflow run"):
        runner.advance("missing")
