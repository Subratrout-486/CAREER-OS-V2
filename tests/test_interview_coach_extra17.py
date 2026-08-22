from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_followups_probe_contribution_result_and_learning():
    followups = InterviewCoachAgent().generate_questions(["SQL"], [])[0].follow_ups
    assert any("contribution" in item for item in followups)
    assert any("result" in item for item in followups)
    assert any("differently" in item for item in followups)
