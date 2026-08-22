from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_answer_specificity_requires_a_numeric_result():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["Python"], [])[0]
    evaluation = agent.evaluate_answer(question, "Situation: task. Action: Python. Result: improved things.", [])
    assert evaluation.score.specificity == 2
