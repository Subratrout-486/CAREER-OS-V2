from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_empty_answer_has_no_strength_summary():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["SQL"], [])[0]
    evaluation = agent.evaluate_answer(question, "", [])
    assert evaluation.strengths == []
