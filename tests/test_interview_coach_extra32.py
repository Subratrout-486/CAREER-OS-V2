from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_question_limit_argument_is_honored():
    agent = InterviewCoachAgent()
    questions = agent.generate_questions(["SQL", "Python", "Excel"], [], limit=2)
    assert len(questions) == 2
