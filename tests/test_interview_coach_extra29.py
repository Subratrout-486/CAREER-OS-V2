from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_evaluation_lists_only_used_evidence():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["SQL"], ["SQL"])[0]
    evaluation = agent.evaluate_answer(question, "I used SQL and got 2 results.", ["SQL", "Python"])
    assert evaluation.evidence_used == ["SQL"]
