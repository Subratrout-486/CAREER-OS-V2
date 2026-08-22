from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_whitespace_only_answer_is_empty():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["SQL"], [])[0]
    evaluation = agent.evaluate_answer(question, "   ", [])
    assert evaluation.score.clarity == 0
