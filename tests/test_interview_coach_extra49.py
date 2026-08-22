from datetime import datetime, timezone
from uuid import uuid4
from career_os.models.interview import AnswerEvaluation, AnswerScore, InterviewSession


def test_session_retains_evaluation_question_id():
    session = InterviewSession(job_id=uuid4(), started_at=datetime.now(timezone.utc))
    question_id = uuid4()
    session.evaluations.append(AnswerEvaluation(question_id=question_id, score=AnswerScore(relevance=5, structure=5, specificity=5, evidence=5, clarity=5)))
    assert session.evaluations[0].question_id == question_id
