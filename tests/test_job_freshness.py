from datetime import datetime, timedelta, timezone

from career_os.agents.job_freshness import Freshness, FreshnessEvaluator
from career_os.agents.job_scout import JobScout
from career_os.models.job import JobStatus


def make_job():
    return JobScout().build_record(
        company="Acme", title="Product Analyst", location="Hyderabad", source_url="https://example.com/jobs/1", source="official"
    )


def test_recent_posting_is_fresh():
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    job = make_job()
    job.posted_at = now - timedelta(days=7)
    assert FreshnessEvaluator().evaluate(job, now=now, max_age_days=45) is Freshness.FRESH


def test_old_posting_is_stale_and_not_verified():
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    job = make_job()
    job.posted_at = now - timedelta(days=60)
    job.status = JobStatus.VERIFIED
    assert FreshnessEvaluator().evaluate(job, now=now, max_age_days=45) is Freshness.STALE
    assert job.status is JobStatus.UNKNOWN
    assert "POSTING_OLDER_THAN_45_DAYS" in job.risk_signals


def test_missing_posted_date_is_unknown_not_fabricated():
    job = make_job()
    assert FreshnessEvaluator().evaluate(job) is Freshness.UNKNOWN
    assert "POSTED_DATE_UNKNOWN" in job.risk_signals
