from career_os.agents.interview_coach_agent import InterviewCoachAgent
from career_os.models.interview import InterviewQuestionType


def test_question_generation_is_role_and_evidence_grounded():
    agent = InterviewCoachAgent()
    questions = agent.generate_questions(["SQL troubleshooting", "incident management"], ["FactSet support tickets", "Oracle SQL"])
    assert len(questions) == 2
    assert questions[0].question_type == InterviewQuestionType.ROLE_SPECIFIC
    assert questions[0].competency == "SQL troubleshooting"
    assert "FactSet support tickets" in questions[0].evidence_basis


def test_answer_evaluation_rewards_structure_specificity_and_evidence():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["SQL troubleshooting"], ["Oracle SQL"])[0]
    answer = "Situation: a ticket failed. Task: investigate. Action: used Oracle SQL. Result: resolved 20 tickets in 2 hours."
    evaluation = agent.evaluate_answer(question, answer, ["Oracle SQL"])
    assert evaluation.score.total == 25
    assert evaluation.evidence_used == ["Oracle SQL"]
    assert not evaluation.gaps


def test_answer_evaluation_flags_weak_answer_without_inventing_claims():
    agent = InterviewCoachAgent()
    question = agent.generate_questions(["Python"], ["Python"])[0]
    evaluation = agent.evaluate_answer(question, "I know Python.", ["Python"])
    assert evaluation.score.total < 25
    assert evaluation.gaps
    assert evaluation.coaching
    assert evaluation.unsupported_claims == []
