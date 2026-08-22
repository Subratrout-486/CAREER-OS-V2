from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_no_competencies_returns_empty_question_list():
    assert InterviewCoachAgent().generate_questions([], ["SQL"]) == []
