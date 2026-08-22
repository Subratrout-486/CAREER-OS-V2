from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_question_text_names_target_competency():
    question = InterviewCoachAgent().generate_questions(["SQL troubleshooting"], [])[0]
    assert "SQL troubleshooting" in question.text
