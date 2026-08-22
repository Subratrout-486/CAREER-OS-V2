from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_evaluation_points_to_question():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["SQL"], ["SQL"])[0]
    evaluation = agent.evaluate_answer(question, "SQL work result 2.", ["SQL"])
    assert evaluation.question_id == question.question_id
