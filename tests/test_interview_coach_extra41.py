from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_answer_relevance_is_high_when_competency_is_present():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["SQL"], [])[0]
    evaluation = agent.evaluate_answer(question, "SQL result 2.", [])
    assert evaluation.score.relevance == 5
