from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_answer_clarity_is_zero_for_empty_answer():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["Python"], [])[0]
    evaluation = agent.evaluate_answer(question, "", [])
    assert evaluation.score.clarity == 0
