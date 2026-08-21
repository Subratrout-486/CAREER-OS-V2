from career_os.agents.job_scout import JobScout
from career_os.models.job import JobStatus, SourceType, canonicalize_url


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
    assert first.source_type is SourceType.OFFICIAL_CAREER_PAGE


def test_ats_source_is_classified_without_browser_dependency():
    job = JobScout().build_record(
        company="Acme", title="Analyst", location="Hyderabad", source_url="https://jobs.lever.co/acme/123", source="search"
    )
    assert job.source_type is SourceType.ATS


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


def test_content_fingerprint_catches_same_listing_with_different_urls():
    scout = JobScout()
    first = scout.build_record(
        company="Acme", title="Product Analyst", location="Hyderabad", source_url="https://a.example/jobs/1", source="board", description="Own product reporting and customer analysis."
    )
    second = scout.build_record(
        company="Acme", title="Product Analyst", location="Hyderabad", source_url="https://b.example/jobs/xyz", source="board", description="Own product reporting and customer analysis."
    )
    records = scout.deduplicate([first, second])
    assert records[1].status is JobStatus.DUPLICATE
    assert records[1].duplicate_of == records[0].job_id


def test_search_result_is_flagged_for_origin_verification():
    job = JobScout().build_record(
        company="Acme", title="Analyst", location="Hyderabad", source_url="https://search.example/job/1", source="google search"
    )
    assert job.source_type is SourceType.SEARCH_RESULT
    assert "SEARCH_RESULT_NEEDS_ORIGIN_VERIFICATION" in job.risk_signals
