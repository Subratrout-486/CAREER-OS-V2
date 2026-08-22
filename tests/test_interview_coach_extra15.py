from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_generated_question_has_default_difficulty():
    question = InterviewCoachAgent().generate_questions(["SQL"], [])[0]
    assert question.difficulty == 2
