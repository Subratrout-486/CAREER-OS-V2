from datetime import datetime, timezone
from pathlib import Path

import pytest

from career_os.application.submission_adapter import ApplicationSubmissionAdapter
from career_os.agents.application_manager import ApplicationManager
from career_os.models.application import ApplicationStatus
from career_os.models.job import JobRecord, SourceType, canonical_job_key


class FakeResult:
    def __init__(self, *, submitted: bool, evidence=(), blockers=(), state="paused"):
        self.submitted = submitted
        self.evidence = list(evidence)
        self.blockers = list(blockers)
        self.state = state


def make_application():
    url = "https://example.com/jobs/123"
    job = JobRecord(
        company="Example Corp",
        title="Product Analyst",
        location="Hyderabad",
        source_url=url,
        source="example",
        source_type=SourceType.OFFICIAL_CAREER_PAGE,
        canonical_key=canonical_job_key("Example Corp", "Product Analyst", "Hyderabad", url),
    )
    manager = ApplicationManager()
    application = manager.create(job, resume_version="resume-v1")
    manager.mark_ready(application)
    manager.approve(application)
    return manager, application, job


def test_executor_persists_only_verified_submission():
    manager, application, job = make_application()
    runner = lambda *_args: FakeResult(
        submitted=True,
        evidence=("https://example.com/confirmation/ABC-123", "application received"),
        state="submitted",
    )
    adapter = ApplicationSubmissionAdapter(manager=manager, runner=runner)

    outcome = adapter.execute(
        application,
        job={"id": str(job.job_id), "application_url": "https://example.com/apply", "application_decision": "approved"},
        profile={"candidate": {"name": "Subrat"}},
        resume_path=str(Path(__file__)),
        submitted_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    assert outcome.submitted is True
    assert application.status == ApplicationStatus.SUBMITTED
    assert application.submission_confirmed_at == datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert len(application.events) == 3


def test_executor_does_not_mark_submission_on_blocker():
    manager, application, job = make_application()
    runner = lambda *_args: FakeResult(
        submitted=False,
        blockers=("Human/security verification is present; automation paused.",),
    )
    adapter = ApplicationSubmissionAdapter(manager=manager, runner=runner)

    outcome = adapter.execute(
        application,
        job={"id": str(job.job_id), "application_url": "https://example.com/apply", "application_decision": "approved"},
        profile={},
        resume_path=str(Path(__file__)),
    )

    assert outcome.submitted is False
    assert application.status == ApplicationStatus.APPROVED
    assert len(application.events) == 2
    assert outcome.blockers


def test_executor_rejects_unapproved_application():
    manager, application, job = make_application()
    application.status = ApplicationStatus.DISCOVERED
    adapter = ApplicationSubmissionAdapter(manager=manager, runner=lambda *_args: None)

    with pytest.raises(ValueError, match="explicitly approved"):
        adapter.execute(
            application,
            job={"id": str(job.job_id), "application_url": "https://example.com/apply"},
            profile={},
            resume_path=str(Path(__file__)),
        )
