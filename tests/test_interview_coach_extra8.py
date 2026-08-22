from career_os.agents.interview_coach_agent import InterviewCoachAgent


def test_question_generation_respects_default_cap():
    agent = InterviewCoachAgent()
    competencies = ["SQL", "Python", "Excel", "Power BI", "REST API", "Unix", "Oracle", "ServiceNow", "Control-M", "ETL", "Testing"]
    questions = agent.generate_questions(competencies)
    assert len(questions) == 10
