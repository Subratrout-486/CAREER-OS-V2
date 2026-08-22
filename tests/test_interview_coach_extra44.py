from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_answer_evidence_matching_is_case_insensitive():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["SQL"], ["Oracle SQL"])[0]
    evaluation = agent.evaluate_answer(question, "I used oracle sql and got 2 results.", ["Oracle SQL"])
    assert evaluation.score.evidence == 5
