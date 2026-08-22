from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_interview_coach_does_not_treat_missing_evidence_as_proof():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["Python"], ["Python"])[0]
    evaluation = agent.evaluate_answer(question, "I know Python.", ["Python"])
    assert evaluation.evidence_used == ["Python"]
    assert "Result" in evaluation.coaching[0] or evaluation.gaps
