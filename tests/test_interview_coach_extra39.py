from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_questions_work_without_evidence():
    question = InterviewCoachAgent().generate_questions(["SQL"], [])[0]
    assert question.evidence_basis == []
