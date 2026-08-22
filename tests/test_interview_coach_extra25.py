from datetime import datetime, timezone
from uuid import uuid4
from career_os.models.interview import AnswerEvaluation, AnswerScore, InterviewSession


def test_session_average_aggregates_multiple_answers():
    session = InterviewSession(job_id=uuid4(), started_at=datetime.now(timezone.utc))
    for _ in range(2):
        session.evaluations.append(AnswerEvaluation(question_id=uuid4(), score=AnswerScore(relevance=5, structure=5, specificity=5, evidence=5, clarity=5)))
    assert session.average_score == 1.0
