from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_weak_answer_gets_measurable_result_coaching():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["Python"], ["Python"])[0]
    evaluation = agent.evaluate_answer(question, "I know Python.", ["Python"])
    assert any("metric" in tip.lower() for tip in evaluation.coaching)
