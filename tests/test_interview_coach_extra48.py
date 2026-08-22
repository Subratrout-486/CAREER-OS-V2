from datetime import datetime, timezone
from uuid import uuid4
from career_os.models.interview import InterviewSession


def test_session_average_is_none_before_answers():
    session = InterviewSession(job_id=uuid4(), started_at=datetime.now(timezone.utc))
    assert session.average_score is None
