from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_generated_question_has_competency_and_evidence():
    question = InterviewCoachAgent().generate_questions(["SQL"], ["Oracle SQL"])[0]
    assert question.competency == "SQL"
    assert question.evidence_basis == ["Oracle SQL"]
