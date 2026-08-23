from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from career_os.agents.follow_up import FollowUpManager
from career_os.models.application import ApplicationRecord, ApplicationStatus


def application(status=ApplicationStatus.SUBMITTED):
    return ApplicationRecord(
        job_id=uuid4(),
        source_url="https://example.com/jobs/123",
        company="Example Co",
        role="Data Analyst",
        status=status,
        submission_confirmed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


def test_schedule_requires_confirmed_submission():
    app = application()
    manager = FollowUpManager()
    manager.schedule_after_submission(app)
    assert app.follow_up_at == datetime(2026, 8, 8, tzinfo=timezone.utc)


def test_schedule_rejects_unsubmitted_application():
    app = application(ApplicationStatus.APPROVED)
    with pytest.raises(ValueError, match="only be scheduled after confirmed submission"):
        FollowUpManager().schedule_after_submission(app)


def test_due_follow_up_is_idempotent():
    manager = FollowUpManager()
    app = application()
    manager.schedule_after_submission(app)
    now = app.follow_up_at + timedelta(minutes=1)
    first = manager.plan(app, now=now)
    second = manager.plan(app, now=now)
    assert first is not None
    assert second == first
    assert len(app.events) == 0


def test_terminal_status_is_never_due():
    manager = FollowUpManager()
    app = application(ApplicationStatus.REJECTED)
    app.follow_up_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    assert manager.due(app, now=datetime(2026, 8, 10, tzinfo=timezone.utc)) is False
    assert manager.plan(app, now=datetime(2026, 8, 10, tzinfo=timezone.utc)) is None


def test_interview_stage_can_be_due():
    manager = FollowUpManager()
    app = application(ApplicationStatus.INTERVIEW)
    app.follow_up_at = datetime(2026, 8, 8, tzinfo=timezone.utc)
    action = manager.plan(app, now=datetime(2026, 8, 9, tzinfo=timezone.utc))
    assert action is not None
    assert "Interview-stage" in action.reason
