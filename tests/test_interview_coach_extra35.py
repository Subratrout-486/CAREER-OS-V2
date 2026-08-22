from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_weak_answer_has_actionable_gaps():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["SQL"], ["SQL"])[0]
    evaluation = agent.evaluate_answer(question, "SQL.", ["SQL"])
    assert len(evaluation.gaps) >= 2
