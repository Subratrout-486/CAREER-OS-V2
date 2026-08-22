from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_answer_evidence_is_only_counted_when_present():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["Python"], ["Python"])[0]
    evaluation = agent.evaluate_answer(question, "I know Python.", ["Python", "SQL"])
    assert evaluation.evidence_used == ["Python"]
    assert evaluation.score.evidence == 5
