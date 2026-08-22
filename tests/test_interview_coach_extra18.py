from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_empty_competencies_produce_no_questions():
    assert InterviewCoachAgent().generate_questions([], []) == []
