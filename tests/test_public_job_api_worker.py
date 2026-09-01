from __future__ import annotations

from career_os.models.job import JobRecord
from scripts import public_job_api_worker as worker


def test_create_notion_job_serializes_pydantic_http_url(monkeypatch):
    captured: dict[str, object] = {}

    def fake_notion_request(method: str, path: str, body: dict[str, object] | None = None):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        return {"id": "notion-page-123"}

    monkeypatch.setattr(worker, "_notion_request", fake_notion_request)
    job = JobRecord(
        company="Example Co",
        title="Support Engineer",
        source_url="https://example.com/jobs/123",
        source="test",
        canonical_key="test-key",
        description="Support enterprise applications.",
    )

    assert worker._create_notion_job(job) == "notion-page-123"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["properties"]["Job URL"]["url"] == "https://example.com/jobs/123"
