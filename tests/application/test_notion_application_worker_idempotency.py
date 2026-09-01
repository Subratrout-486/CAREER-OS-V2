from types import SimpleNamespace

import scripts.notion_application_worker as worker


def test_existing_application_matches_job_url_regardless_of_status(monkeypatch):
    calls = []

    def request(method, path, body):
        calls.append((method, path, body))
        return {"results": [
            {"id": "page-1", "properties": {
                "Job URL": {"type": "url", "url": "https://example.com/jobs/1"},
                "Status": {"type": "select", "select": {"name": "Ready"}},
            }}
        ]}

    monkeypatch.setattr(worker.notion_job_worker, "notion_request", request)
    existing = worker._existing_application("https://example.com/jobs/1")
    assert existing["id"] == "page-1"
    assert calls[0][2] == {"page_size": 100}


def test_create_application_updates_existing_record_instead_of_creating_duplicate(monkeypatch):
    calls = []
    job = {"properties": {
        "Job": {"type": "title", "title": [{"plain_text": "Engineer"}]},
        "Company": {"type": "rich_text", "rich_text": [{"plain_text": "Example"}]},
        "Job URL": {"type": "url", "url": "https://example.com/jobs/1"},
        "Application URL": {"type": "url", "url": "https://example.com/apply/1"},
    }}
    result = SimpleNamespace(evidence=["https://example.com/confirmation/1"])

    def request(method, path, body):
        calls.append((method, path, body))
        if path.startswith("/data_sources/"):
            return {"results": [{"id": "page-1", "properties": {
                "Job URL": {"type": "url", "url": "https://example.com/jobs/1"},
                "Status": {"type": "select", "select": {"name": "Ready"}},
            }}]}
        return {"id": "unexpected"}

    monkeypatch.setattr(worker.notion_job_worker, "notion_request", request)
    page_id = worker._create_application(job, result, "resume.pdf")

    assert page_id == "page-1"
    assert any(method == "PATCH" and path == "/pages/page-1" for method, path, _ in calls)
    assert not any(method == "POST" and path == "/pages" for method, path, _ in calls)
