from datetime import datetime, timezone
from uuid import uuid4

import pytest

from career_os.models.application import ApplicationRecord, ApplicationStatus


def make_application() -> ApplicationRecord:
    return ApplicationRecord(
        job_id=uuid4(),
        source_url="https://example.com/jobs/123",
        company="Example Corp",
        role="Product Analyst",
        resume_version="resume-v1",
    )


def test_application_follows_auditable_state_machine():
    app = make_application()
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)

    app.transition(ApplicationStatus.READY_FOR_REVIEW, note="Reviewer cleared")
    app.transition(ApplicationStatus.APPROVED, note="Candidate approved")
    event = app.transition(
        ApplicationStatus.SUBMITTED,
        evidence="portal confirmation: ABC-123",
        now=now,
    )

    assert app.status == ApplicationStatus.SUBMITTED
    assert app.submission_confirmed_at == now
    assert len(app.events) == 3
    assert event.evidence == "portal confirmation: ABC-123"
    assert [(e.from_status, e.to_status) for e in app.events] == [
        (ApplicationStatus.DISCOVERED, ApplicationStatus.READY_FOR_REVIEW),
        (ApplicationStatus.READY_FOR_REVIEW, ApplicationStatus.APPROVED),
        (ApplicationStatus.APPROVED, ApplicationStatus.SUBMITTED),
    ]


def test_submission_requires_confirmation_evidence():
    app = make_application()
    app.transition(ApplicationStatus.READY_FOR_REVIEW)
    app.transition(ApplicationStatus.APPROVED)

    with pytest.raises(ValueError, match="confirmed submission requires evidence"):
        app.transition(ApplicationStatus.SUBMITTED)

    assert app.status == ApplicationStatus.APPROVED
    assert app.submission_confirmed_at is None
    assert len(app.events) == 2


def test_invalid_transition_is_rejected_without_mutating_history():
    app = make_application()

    with pytest.raises(ValueError, match="Invalid application transition"):
        app.transition(ApplicationStatus.SUBMITTED, evidence="confirmation")

    assert app.status == ApplicationStatus.DISCOVERED
    assert app.events == []


def test_terminal_application_cannot_be_reopened():
    app = make_application()
    app.transition(ApplicationStatus.WITHDRAWN, note="Candidate withdrew")

    with pytest.raises(ValueError, match="terminal application"):
        app.transition(ApplicationStatus.READY_FOR_REVIEW)

    assert app.status == ApplicationStatus.WITHDRAWN
    assert len(app.events) == 1
