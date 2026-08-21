from career_os.agents.job_scout import JobScout
from career_os.agents.job_verification import JobVerifier
from career_os.models.job import JobStatus


def make_job(url: str):
    return JobScout().build_record(
        company="Example", title="Analyst", location="Hyderabad", source_url=url, source="official"
    )


def test_404_is_classified_as_ghost(monkeypatch):
    from urllib.error import HTTPError

    def fail(*args, **kwargs):
        raise HTTPError("https://example.com/job", 404, "Not Found", {}, None)

    monkeypatch.setattr("career_os.agents.job_verification.urlopen", fail)
    job = JobVerifier().verify_url(make_job("https://example.com/job"))
    assert job.status is JobStatus.GHOST
    assert job.verification_evidence[-1].signal == "url_http_error"


def test_network_failure_remains_unknown(monkeypatch):
    from urllib.error import URLError

    def fail(*args, **kwargs):
        raise URLError("blocked")

    monkeypatch.setattr("career_os.agents.job_verification.urlopen", fail)
    job = JobVerifier().verify_url(make_job("https://example.com/job"))
    assert job.status is JobStatus.UNKNOWN
    assert job.verification_evidence[-1].signal == "url_unreachable"
