from career_os.agents.ats_job_scout import ATSJobScout
from career_os.integrations.ats import RawATSJob
from career_os.models.job import JobStatus


def test_ats_job_scout_feeds_records_into_canonical_intake():
    raw = RawATSJob(
        provider="greenhouse",
        external_id="123",
        company="Acme",
        title="Product Support Analyst",
        location="Hyderabad",
        description="SQL troubleshooting and customer support",
        job_url="https://boards.greenhouse.io/acme/jobs/123",
        posted_at="2026-08-21T00:00:00Z",
        raw={"id": 123},
    )

    records = ATSJobScout().ingest([raw])

    assert len(records) == 1
    assert records[0].company == "Acme"
    assert records[0].title == "Product Support Analyst"
    assert str(records[0].source_url) == raw.job_url
    assert records[0].status is not JobStatus.DUPLICATE
