from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_question_has_three_followups():
    question = InterviewCoachAgent().generate_questions(["SQL"], [])[0]
    assert len(question.follow_ups) == 3
