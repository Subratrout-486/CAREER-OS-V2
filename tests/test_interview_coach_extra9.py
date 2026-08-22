from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_generated_questions_include_follow_ups():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["SQL"], ["SQL"])[0]
    assert len(question.follow_ups) == 3
