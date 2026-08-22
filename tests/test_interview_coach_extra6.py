from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_empty_answer_does_not_claim_success():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["Python"], ["Python"])[0]
    evaluation = agent.evaluate_answer(question, "", ["Python"])
    assert evaluation.score.clarity == 0
    assert evaluation.strengths == []
