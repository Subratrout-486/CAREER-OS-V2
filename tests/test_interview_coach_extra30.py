from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_complete_star_answer_gets_full_structure_score():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["SQL"], [])[0]
    evaluation = agent.evaluate_answer(question, "Situation SQL. Task SQL. Action SQL. Result 2.", [])
    assert evaluation.score.structure == 5
