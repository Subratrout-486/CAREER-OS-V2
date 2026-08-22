from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_weak_answer_reports_result_gap():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["Python"], ["Python"])[0]
    evaluation = agent.evaluate_answer(question, "I know Python.", ["Python"])
    assert any("measurable result" in gap for gap in evaluation.gaps)
