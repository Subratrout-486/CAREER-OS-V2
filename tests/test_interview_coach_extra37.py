from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_nonempty_answer_has_strength_summary():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["SQL"], ["SQL"])[0]
    evaluation = agent.evaluate_answer(question, "SQL.", ["SQL"])
    assert evaluation.strengths == ["Answer was provided."]
