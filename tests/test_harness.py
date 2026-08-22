from career_os.harness import ActionPolicy, AgentContext, AgentHarness, AgentState, Event, RiskLevel, ToolRequest


def test_low_risk_request_is_returned_without_approval():
    planner = lambda context, events: ToolRequest("read_jd", risk="low")
    harness = AgentHarness(AgentContext("analyze JD"), ActionPolicy(), planner)

    request = harness.step()

    assert request is not None
    assert request.name == "read_jd"
    assert harness.state == AgentState.RUNNING
    assert not any(e.kind == "approval.required" for e in harness.events.snapshot())


def test_high_risk_request_pauses_and_requires_explicit_approval():
    planner = lambda context, events: ToolRequest("submit_application", risk="high")
    harness = AgentHarness(AgentContext("apply"), ActionPolicy(), planner)

    request = harness.step()

    assert request is not None
    assert harness.state == AgentState.WAITING_APPROVAL
    assert harness.pending == request
    assert harness.events.snapshot()[-1].kind == "approval.required"

    approved = harness.approve()
    assert approved == request
    assert harness.state == AgentState.RUNNING


def test_rejection_is_terminal_and_audited():
    planner = lambda context, events: ToolRequest("submit_application", risk=RiskLevel.HIGH)
    harness = AgentHarness(AgentContext("apply"), ActionPolicy(), planner)

    harness.step()
    harness.reject()

    assert harness.state == AgentState.FAILED
    assert harness.events.snapshot()[-1].kind == "approval.rejected"


def test_none_from_planner_completes_run():
    planner = lambda context, events: None
    harness = AgentHarness(AgentContext("finish"), ActionPolicy(), planner)

    assert harness.step() is None
    assert harness.state == AgentState.COMPLETED
    completed = harness.events.snapshot()[-1]
    assert completed.kind == "run.completed"
    assert completed.payload == {}
    assert completed.event_id
