from career_os.agents.job_scout import JobScout
from career_os.models.job import JobStatus, canonicalize_url


URL = "https://example.com/jobs/123/?utm_source=linkedin&ref=abc"


def test_url_canonicalization_removes_tracking_parameters():
    assert canonicalize_url(URL) == "https://example.com/jobs/123/"


def test_job_scout_creates_stable_canonical_identity():
    scout = JobScout()
    first = scout.build_record(
        company="Acme", title="Product Support Engineer", location="Hyderabad", source_url=URL, source="official"
    )
    second = scout.build_record(
        company="Acme", title="Product Support Engineer", location="Hyderabad", source_url="https://example.com/jobs/123", source="official"
    )
    assert first.canonical_key == second.canonical_key


def test_job_scout_marks_duplicate_without_deleting_the_record():
    scout = JobScout()
    first = scout.build_record(
        company="Acme", title="Analyst", location="Hyderabad", source_url="https://example.com/jobs/1", source="official"
    )
    second = scout.build_record(
        company="Acme", title="Analyst", location="Hyderabad", source_url="https://example.com/jobs/1?utm_medium=jobboard", source="jobboard"
    )
    records = scout.deduplicate([first, second])
    assert records[0].status is JobStatus.UNKNOWN
    assert records[1].status is JobStatus.DUPLICATE
    assert records[1].duplicate_of == records[0].job_id
