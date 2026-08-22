from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_generated_questions_have_distinct_ids():
    questions = InterviewCoachAgent().generate_questions(["SQL", "Python"], [])
    assert questions[0].question_id != questions[1].question_id
