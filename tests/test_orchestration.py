from career_os.orchestration.repository import InMemoryWorkflowRepository
from career_os.orchestration.workflow import (
    NodeOutcome,
    RunStatus,
    WorkflowNode,
    WorkflowOrchestrator,
)


def test_sequential_workflow_completes_and_is_idempotent() -> None:
    calls: list[str] = []
    workflow = WorkflowOrchestrator(
        [
            WorkflowNode("discover", lambda _: calls.append("discover") or NodeOutcome.NEXT),
            WorkflowNode("score", lambda _: calls.append("score") or NodeOutcome.COMPLETE),
        ]
    )

    state = workflow.run(workflow.start("run-1"))
    assert state.status is RunStatus.COMPLETED
    assert calls == ["discover", "score"]

    workflow.run(state)
    assert calls == ["discover", "score"]


def test_approval_resumes_same_node_then_continues() -> None:
    calls: list[str] = []

    def apply(_: object) -> NodeOutcome:
        calls.append("apply")
        return NodeOutcome.NEXT

    workflow = WorkflowOrchestrator(
        [
            WorkflowNode("prepare", lambda _: calls.append("prepare") or NodeOutcome.NEXT),
            WorkflowNode("apply", apply, requires_approval=True),
            WorkflowNode("finish", lambda _: calls.append("finish") or NodeOutcome.COMPLETE),
        ]
    )

    state = workflow.run(workflow.start("run-approval"))
    assert state.status is RunStatus.WAITING_APPROVAL
    assert calls == ["prepare"]

    state = workflow.run(state, approval=True)
    assert state.status is RunStatus.COMPLETED
    assert calls == ["prepare", "apply", "finish"]


def test_input_gate_is_distinct_and_resumable() -> None:
    def needs_input(state) -> NodeOutcome:
        if "input:question" not in state.context:
            return NodeOutcome.AWAIT_INPUT
        return NodeOutcome.NEXT

    workflow = WorkflowOrchestrator(
        [
            WorkflowNode("question", needs_input),
            WorkflowNode("finish", lambda _: NodeOutcome.COMPLETE),
        ]
    )

    state = workflow.run(workflow.start("run-input"))
    assert state.status is RunStatus.WAITING_INPUT
    assert state.input_node == "question"

    state = workflow.run(state, input_value="yes")
    assert state.status is RunStatus.COMPLETED
    assert state.context["input:question"] == "yes"


def test_retry_is_bounded_without_recursion() -> None:
    attempts = 0

    def flaky(_: object) -> NodeOutcome:
        nonlocal attempts
        attempts += 1
        return NodeOutcome.RETRY

    workflow = WorkflowOrchestrator([WorkflowNode("flaky", flaky, max_attempts=3)])
    state = workflow.run(workflow.start("run-retry"))

    assert state.status is RunStatus.FAILED
    assert attempts == 3
    assert state.attempts["flaky"] == 3


def test_rejected_approval_fails_and_is_terminal() -> None:
    workflow = WorkflowOrchestrator(
        [WorkflowNode("dangerous", lambda _: NodeOutcome.COMPLETE, requires_approval=True)]
    )

    state = workflow.run(workflow.start("run-reject"))
    state = workflow.run(state, approval=False)
    assert state.status is RunStatus.FAILED
    assert workflow.run(state, approval=True).status is RunStatus.FAILED


def test_repository_round_trip_isolated_from_mutation() -> None:
    repo = InMemoryWorkflowRepository()
    workflow = WorkflowOrchestrator([WorkflowNode("finish", lambda _: NodeOutcome.COMPLETE)])

    state = workflow.run(workflow.start("run-store", context={"x": 1}))
    repo.save(state)
    loaded = repo.get("run-store")

    assert loaded is not None
    assert loaded.context == {"x": 1}
    loaded.context["x"] = 99
    stored = repo.get("run-store")
    assert stored is not None
    assert stored.context == {"x": 1}
