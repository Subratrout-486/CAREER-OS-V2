from career_os.integrations.ats import (
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
    client = FakeClient([{"id": "abc", "text": "Support Engineer", "categories": {"location": "Hyderabad"}, "hostedUrl": "https://jobs.lever.co/acme/abc", "createdAt": 1776600000000}])
    jobs = LeverAdapter(client).fetch("acme")
    assert jobs[0].posted_at == "2026-04-19T12:00:00Z"


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
