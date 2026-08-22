from career_os.agents.job_intake import JobIntakePipeline
from career_os.models.job import JobStatus, SourceType


def test_ats_record_normalizes_into_canonical_job():
    pipeline = JobIntakePipeline()
    job = pipeline.normalize(
        {
            "company": "Acme",
            "title": "Product Support Engineer",
            "location": "Hyderabad",
            "url": "https://jobs.example.com/123?utm_source=ats",
            "provider": "greenhouse",
            "description": "Support enterprise customers and troubleshoot product issues.",
            "published_at": "2026-08-20T10:00:00Z",
        }
    )
    assert job.source_type is SourceType.ATS
    assert job.content_fingerprint
    assert job.posted_at is not None


def test_same_content_at_different_urls_is_deduplicated():
    pipeline = JobIntakePipeline()
    rows = [
        {
            "company": "Acme",
            "title": "Product Support Engineer",
            "location": "Hyderabad",
            "url": "https://jobs.greenhouse.io/acme/123",
            "provider": "greenhouse",
            "description": "Support enterprise customers and troubleshoot product issues.",
        },
        {
            "company": "Acme",
            "title": "Product Support Engineer",
            "location": "Hyderabad",
            "url": "https://jobs.lever.co/acme/abc",
            "provider": "lever",
            "description": "Support enterprise customers and troubleshoot product issues.",
        },
    ]
    jobs = pipeline.ingest(rows)
    assert jobs[0].status is JobStatus.NEW
    assert jobs[1].status is JobStatus.DUPLICATE
    assert jobs[1].duplicate_of == jobs[0].job_id
    assert "CONTENT_DUPLICATE" in jobs[1].risk_signals


def test_missing_posted_date_is_not_invented():
    job = JobIntakePipeline().normalize(
        {
            "company": "Acme",
            "title": "Analyst",
            "location": "Hyderabad",
            "url": "https://jobs.example.com/1",
            "provider": "ashby",
        }
    )
    assert job.posted_at is None
