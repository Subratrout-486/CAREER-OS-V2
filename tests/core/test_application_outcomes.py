from career_os.core.application_outcomes import ApplicationOutcomeAnalyzer
from career_os.models.application import ApplicationRecord, ApplicationStatus
from career_os.models.job import JobRecord


def _app(status: ApplicationStatus) -> ApplicationRecord:
    job = JobRecord(company="Acme", title="Analyst", source_url="https://example.com/job")
    app = ApplicationRecord(job_id=job.job_id, source_url=job.source_url, company=job.company, role=job.title)
    if status == ApplicationStatus.REJECTED:
        app.transition(ApplicationStatus.READY_FOR_REVIEW)
        app.transition(ApplicationStatus.APPROVED)
        app.transition(ApplicationStatus.SUBMITTED, evidence="confirmation")
        app.transition(ApplicationStatus.REJECTED, note="requirements mismatch")
    return app


def test_outcome_summary_counts_recorded_states():
    apps = [_app(ApplicationStatus.REJECTED), _app(ApplicationStatus.DISCOVERED)]
    summary = ApplicationOutcomeAnalyzer().summarize(apps)
    assert summary.total == 2
    assert summary.submitted == 1
    assert summary.rejected == 1
    assert summary.submission_rate == 0.5
    assert summary.interview_rate == 0.0


def test_rejection_reason_uses_only_explicit_notes():
    counts = ApplicationOutcomeAnalyzer().rejection_counts([_app(ApplicationStatus.REJECTED)])
    assert counts["requirements mismatch"] == 1
