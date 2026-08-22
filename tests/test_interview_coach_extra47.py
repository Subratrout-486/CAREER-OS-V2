from datetime import datetime, timezone
from uuid import uuid4
from career_os.models.interview import AnswerEvaluation, AnswerScore, InterviewSession


def test_session_average_score_is_decimal_ratio():
    session = InterviewSession(job_id=uuid4(), started_at=datetime.now(timezone.utc))
    session.evaluations.append(AnswerEvaluation(question_id=uuid4(), score=AnswerScore(relevance=4, structure=4, specificity=4, evidence=4, clarity=4)))
    assert session.average_score == 0.8
