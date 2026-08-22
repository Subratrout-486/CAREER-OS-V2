from datetime import datetime, timezone
from uuid import uuid4

from career_os.models.interview import InterviewSession


def test_empty_interview_session_has_no_average():
    session = InterviewSession(job_id=uuid4(), started_at=datetime.now(timezone.utc))
    assert session.average_score is None
