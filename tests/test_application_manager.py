from datetime import datetime, timezone

from career_os.agents.application_manager import ApplicationManager
from career_os.models.application import ApplicationStatus
from career_os.models.job import JobRecord, SourceType, canonical_job_key


def make_job() -> JobRecord:
    url = "https://example.com/jobs/123"
    return JobRecord(
        company="Example Corp",
        title="Product Analyst",
        location="Hyderabad",
        source_url=url,
        source="example",
        source_type=SourceType.OFFICIAL_CAREER_PAGE,
        canonical_key=canonical_job_key("Example Corp", "Product Analyst", "Hyderabad", url),
    )


def test_manager_requires_clean_readiness_before_approval():
    manager = ApplicationManager()
    app = manager.create(make_job(), resume_version="resume-v1")

    manager.mark_ready(app, ["Missing required Python evidence"])

    assert app.status == ApplicationStatus.DISCOVERED
    assert not manager.is_submission_ready(app)


def test_manager_requires_explicit_approval_before_submission():
    manager = ApplicationManager()
    app = manager.create(make_job(), resume_version="resume-v1")
    manager.mark_ready(app)

    assert app.status == ApplicationStatus.READY_FOR_REVIEW
    assert not manager.is_submission_ready(app)

    manager.approve(app, note="User approved submission")
    assert manager.is_submission_ready(app)

    submitted_at = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
    manager.confirm_submission(app, confirmation_evidence="Portal confirmation #123", submitted_at=submitted_at)

    assert app.status == ApplicationStatus.SUBMITTED
    assert app.submission_confirmed_at == submitted_at
