import json

import pytest

import career_os.integrations.ats as ats
from career_os.integrations.ats import (
    ATSClient,
    AshbyAdapter,
    GreenhouseAdapter,
    LeverAdapter,
    RipplingAdapter,
    WorkdayAdapter,
    detect_ats,
)


class FakeClient:
    def __init__(self, payloads):
        self.payloads = list(payloads) if isinstance(payloads, list) else [payloads]
        self.urls = []

    def fetch_json(self, url, **kwargs):
        self.urls.append(("GET", url))
        return self.payloads.pop(0)

    def post_json(self, url, payload, **kwargs):
        self.urls.append(("POST", url, payload))
        return self.payloads.pop(0)


def test_detect_ats_from_public_board_urls():
    assert detect_ats("https://boards.greenhouse.io/acme") == ("greenhouse", "acme")
    assert detect_ats("https://jobs.lever.co/acme") == ("lever", "acme")
    assert detect_ats("https://jobs.ashbyhq.com/acme") == ("ashby", "acme")
    assert detect_ats("https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers") == (
        "workday",
        "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers",
    )
    assert detect_ats("https://api.rippling.com/platform/api/ats/v1/board/acme/jobs") == (
        "rippling",
        "jobs",
    )
    assert detect_ats("https://example.com/careers") is None


def test_greenhouse_prefers_first_published():
    client = FakeClient({"jobs": [{"id": 123, "title": "Analyst", "location": {"name": "Hyderabad"}, "absolute_url": "https://example/jobs/123", "content": "JD", "first_published": "2026-08-20T00:00:00Z", "updated_at": "2026-08-21T00:00:00Z"}]})
    jobs = GreenhouseAdapter(client).fetch("acme")
    assert jobs[0].posted_at == "2026-08-20T00:00:00Z"


def test_lever_converts_epoch_milliseconds_to_iso():
    # Lever's public postings endpoint is an array of posting objects.
    client = FakeClient([[{"id": "abc", "text": "Support Engineer", "categories": {"location": "Hyderabad"}, "hostedUrl": "https://jobs.lever.co/acme/abc", "createdAt": 1776600000000}]])
    jobs = LeverAdapter(client).fetch("acme")
    assert jobs[0].posted_at == "2026-04-19T12:00:00Z"


def test_lever_accepts_jobs_wrapper_from_cached_payloads():
    client = FakeClient({"jobs": [{"id": "abc", "text": "Support Engineer", "categories": {"location": "Hyderabad"}, "hostedUrl": "https://jobs.lever.co/acme/abc", "createdAt": 1776600000000}]})
    jobs = LeverAdapter(client).fetch("acme")
    assert jobs[0].external_id == "abc"


def test_ashby_uses_published_at():
    client = FakeClient({"jobs": [{"title": "PM", "location": "Hyderabad", "jobUrl": "https://jobs.ashbyhq.com/acme/1", "publishedAt": "2026-08-21T00:00:00Z"}]})
    jobs = AshbyAdapter(client).fetch("acme")
    assert jobs[0].posted_at == "2026-08-21T00:00:00Z"


def test_workday_builds_cxs_endpoint_and_paginates():
    board = "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers"
    first = {"jobPostings": [{"title": "Product Analyst", "locationsText": "Hyderabad", "externalPath": "/job/123_Product-Analyst", "postedOn": "2026-08-21"}]}
    second = {"jobPostings": []}
    client = FakeClient([first, second])
    jobs = WorkdayAdapter(client).fetch(board, limit=20, max_jobs=50)
    assert jobs[0].provider == "workday"
    assert jobs[0].external_id == "Product-Analyst"
    assert jobs[0].job_url == "https://acme.wd5.myworkdayjobs.com/job/123_Product-Analyst"
    assert client.urls[0][0] == "POST"
    assert "/wday/cxs/acme/AcmeCareers/jobs" in client.urls[0][1]
    assert client.urls[0][2]["limit"] == 20


def test_workday_rejects_page_size_above_public_limit():
    board = "https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers"
    try:
        WorkdayAdapter(FakeClient([])).fetch(board, limit=21)
    except ValueError as exc:
        assert "between 1 and 20" in str(exc)
    else:
        raise AssertionError("expected Workday page-size validation")


def test_rippling_normalizes_common_fields():
    client = FakeClient({"jobs": [{"id": "r1", "title": "Support Engineer", "location": "Hyderabad", "description": "JD", "jobUrl": "https://jobs.rippling.com/acme/r1", "publishedAt": "2026-08-21T00:00:00Z"}]})
    jobs = RipplingAdapter(client).fetch("acme")
    assert jobs[0].provider == "rippling"
    assert jobs[0].external_id == "r1"
    assert jobs[0].job_url.endswith("/r1")
    assert jobs[0].posted_at == "2026-08-21T00:00:00Z"


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"jobs": []}).encode()


def test_ats_client_retries_transient_http_error(monkeypatch):
    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] < 3:
            from urllib.error import HTTPError
            raise HTTPError(request.full_url, 503, "temporary", {}, None)
        return _Response()

    sleeps = []
    monkeypatch.setattr(ats, "urlopen", fake_urlopen)
    monkeypatch.setattr(ats.time, "sleep", sleeps.append)

    payload = ATSClient(retries=2, backoff_seconds=0.1).fetch_json("https://example.com/jobs")

    assert payload == {"jobs": []}
    assert calls["count"] == 3
    assert sleeps == [0.1, 0.2]


def test_ats_client_does_not_retry_non_transient_http_error(monkeypatch):
    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        from urllib.error import HTTPError
        raise HTTPError(request.full_url, 404, "not found", {}, None)

    monkeypatch.setattr(ats, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="HTTP 404"):
        ATSClient(retries=3).fetch_json("https://example.com/missing")
    assert calls["count"] == 1


def test_ats_client_rejects_invalid_retry_configuration():
    with pytest.raises(ValueError):
        ATSClient(retries=-1)
    with pytest.raises(ValueError):
        ATSClient(backoff_seconds=-0.1)
