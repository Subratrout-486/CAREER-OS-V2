from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_answer_without_evidence_scores_evidence_low():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["SQL"], [])[0]
    evaluation = agent.evaluate_answer(question, "SQL result 2.", [])
    assert evaluation.score.evidence == 1
