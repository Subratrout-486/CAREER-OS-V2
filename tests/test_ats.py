from career_os.integrations.ats import AshbyAdapter, GreenhouseAdapter, LeverAdapter, detect_ats


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def fetch_json(self, url, **kwargs):
        self.urls.append(url)
        return self.payload


def test_detect_ats_from_public_board_urls():
    assert detect_ats("https://boards.greenhouse.io/acme") == ("greenhouse", "acme")
    assert detect_ats("https://jobs.lever.co/acme") == ("lever", "acme")
    assert detect_ats("https://jobs.ashbyhq.com/acme") == ("ashby", "acme")
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
