from datetime import datetime, timezone
from uuid import uuid4
from career_os.models.interview import InterviewSession


def test_interview_sessions_have_distinct_ids():
    now = datetime.now(timezone.utc)
    first = InterviewSession(job_id=uuid4(), started_at=now)
    second = InterviewSession(job_id=uuid4(), started_at=now)
    assert first.session_id != second.session_id
