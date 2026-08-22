from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_answer_relevance_is_lower_when_competency_is_absent():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["Python"], [])[0]
    evaluation = agent.evaluate_answer(question, "I managed a project.", [])
    assert evaluation.score.relevance == 2
