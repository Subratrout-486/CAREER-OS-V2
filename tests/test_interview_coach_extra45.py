from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_question_competency_is_preserved_exactly():
    question = InterviewCoachAgent().generate_questions(["SQL Troubleshooting"], [])[0]
    assert question.competency == "SQL Troubleshooting"
