from __future__ import annotations

import json


def test_ci_defers_approved_applications_without_browser(monkeypatch, tmp_path):
    from scripts import notion_application_worker as worker

    report = tmp_path / "application-worker-report.json"
    candidate = {
        "id": "job-1",
        "properties": {
            "Processing Stage": {"type": "select", "select": {"name": "Ready to Apply"}},
            "Status": {"type": "select", "select": {"name": "Ready to Apply"}},
            "Resume Status": {"type": "select", "select": {"name": "Ready"}},
            "Fit Decision": {"type": "select", "select": {"name": "Apply"}},
            "Application URL": {"type": "url", "url": "https://example.com/apply"},
            "Job": {"type": "title", "title": [{"plain_text": "Backend Engineer"}]},
            "Company": {"type": "rich_text", "rich_text": [{"plain_text": "Example"}]},
        },
    }

    monkeypatch.setenv("CI", "true")
    monkeypatch.delenv("APPLICATION_BROWSER_CDP_URL", raising=False)
    monkeypatch.setattr(worker, "REPORT", report)
    monkeypatch.setattr(worker, "load_candidate_source_of_truth", lambda: {"candidate": {"name": "Test"}})
    monkeypatch.setattr(worker, "_eligible_jobs", lambda: [candidate])

    class FailingAdapter:
        def __init__(self):
            raise AssertionError("CI must not instantiate the browser submission adapter")

    monkeypatch.setattr(worker, "ApplicationSubmissionAdapter", FailingAdapter)

    assert worker.main() == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["success"] is True
    assert payload["candidates"] == 1
    assert payload["results"][0]["state"] == "deferred"
    assert payload["results"][0]["submitted"] is False
