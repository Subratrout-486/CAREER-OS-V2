from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_question_evidence_is_bounded():
    evidence = [str(i) for i in range(10)]
    question = InterviewCoachAgent().generate_questions(["SQL"], evidence)[0]
    assert len(question.evidence_basis) == 3
