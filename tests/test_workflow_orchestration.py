from career_os.orchestration.workflow import (
    NodeOutcome,
    RunStatus,
    WorkflowNode,
    WorkflowOrchestrator,
)


def test_linear_workflow_completes_and_records_audit():
    seen = []

    def first(state):
        seen.append("first")
        return NodeOutcome.NEXT

    def second(state):
        seen.append("second")
        return NodeOutcome.COMPLETE

    state = WorkflowOrchestrator([
        WorkflowNode("first", first),
        WorkflowNode("second", second),
    ]).run(WorkflowOrchestrator([WorkflowNode("first", first), WorkflowNode("second", second)]).start("r1"))

    assert state.status is RunStatus.COMPLETED
    assert seen == ["first", "second"]
    assert [event.node for event in state.events] == ["first", "second"]


def test_approval_gate_pauses_and_resumes_without_repeating_prior_node():
    seen = []

    def prepare(state):
        seen.append("prepare")
        return NodeOutcome.NEXT

    def execute(state):
        seen.append("execute")
        return NodeOutcome.COMPLETE

    orchestrator = WorkflowOrchestrator([
        WorkflowNode("prepare", prepare),
        WorkflowNode("execute", execute, requires_approval=True),
    ])
    state = orchestrator.run(orchestrator.start("r2"))
    assert state.status is RunStatus.WAITING_APPROVAL
    assert seen == ["prepare"]

    state = orchestrator.run(state, approval=True)
    assert state.status is RunStatus.COMPLETED
    assert seen == ["prepare", "execute"]


def test_rejected_approval_fails_without_execution():
    executed = []
    orchestrator = WorkflowOrchestrator([
        WorkflowNode("execute", lambda state: (executed.append(True) or NodeOutcome.COMPLETE), requires_approval=True),
    ])
    state = orchestrator.run(orchestrator.start("r3"))
    state = orchestrator.run(state, approval=False)
    assert state.status is RunStatus.FAILED
    assert executed == []


def test_completed_workflow_is_idempotent_on_replay():
    calls = []
    orchestrator = WorkflowOrchestrator([
        WorkflowNode("once", lambda state: (calls.append(True) or NodeOutcome.COMPLETE)),
    ])
    state = orchestrator.run(orchestrator.start("r4"))
    replay = orchestrator.run(state)
    assert replay is state
    assert len(calls) == 1


def test_retry_is_bounded():
    calls = []

    def flaky(state):
        calls.append(True)
        return NodeOutcome.RETRY

    orchestrator = WorkflowOrchestrator([WorkflowNode("flaky", flaky, max_attempts=2)])
    state = orchestrator.run(orchestrator.start("r5"))
    assert state.status is RunStatus.FAILED
    assert len(calls) == 2
