from career_os.integrations.public_ats import SmartRecruitersAdapter, TeamtailorRSSAdapter, detect_public_provider


class FakeClient:
    def __init__(self, payload=None, text=""):
        self.payload = payload
        self.text = text

    def fetch_json(self, url: str):
        return self.payload

    def fetch_text(self, url: str):
        return self.text


def test_smartrecruiters_normalizes_public_postings():
    client = FakeClient({"content": [{"id": "ignored", "name": "Data Analyst", "location": {"city": "Hyderabad"}, "releasedDate": "2026-08-23T00:00:00Z", "ref": {"id": "123", "jobAdUrl": "https://jobs.example/123"}}]})
    jobs = SmartRecruitersAdapter(client).fetch("example")
    assert len(jobs) == 1
    assert jobs[0].provider == "smartrecruiters"
    assert jobs[0].external_id == "123"
    assert jobs[0].title == "Data Analyst"
    assert jobs[0].location == "Hyderabad"


def test_teamtailor_rss_normalizes_public_feed():
    xml = """<?xml version='1.0'?><rss><channel><item><title>Product Analyst</title><link>https://example.teamtailor.com/jobs/1</link><guid>1</guid><description>Analyze product data</description><pubDate>Sun, 23 Aug 2026 00:00:00 GMT</pubDate></item></channel></rss>"""
    jobs = TeamtailorRSSAdapter(FakeClient(text=xml)).fetch("https://example.teamtailor.com")
    assert len(jobs) == 1
    assert jobs[0].provider == "teamtailor"
    assert jobs[0].title == "Product Analyst"
    assert jobs[0].job_url.endswith("/jobs/1")


def test_public_provider_detection():
    assert detect_public_provider("https://example.teamtailor.com") == ("teamtailor", "https://example.teamtailor.com")
    assert detect_public_provider("https://jobs.smartrecruiters.com/Example") == ("smartrecruiters", "Example")
