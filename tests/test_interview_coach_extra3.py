from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_interview_score_is_bounded():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["Python"], ["Python"])[0]
    evaluation = agent.evaluate_answer(question, "I know Python.", ["Python"])
    assert 0 <= evaluation.score.total <= 25
