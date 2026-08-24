from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "notion_job_worker.py"
spec = importlib.util.spec_from_file_location("notion_job_worker", MODULE_PATH)
assert spec is not None and spec.loader is not None
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def page(job: str, stage: str | None = None, status: str | None = None, jd: str | None = None):
    properties = {
        "Job": {"type": "title", "title": [{"plain_text": job}]},
        "Processing Stage": {"type": "select", "select": {"name": stage} if stage else None},
        "Status": {"type": "select", "select": {"name": status} if status else None},
    }
    if jd is not None:
        properties["JD"] = {"type": "rich_text", "rich_text": [{"plain_text": jd}]}
    return {"id": f"page-{job}", "properties": properties}


def test_blank_stage_is_queued_but_terminal_status_is_not(monkeypatch):
    monkeypatch.setattr(
        worker,
        "notion_request",
        lambda *args, **kwargs: {
            "results": [
                page("New manual job", None, "Verified Active"),
                page("Already applied", None, "Applied"),
                page("Closed job", "Verified", "Closed"),
                page("Verified job", "Verified", "Verified Active"),
            ],
            "has_more": False,
        },
    )
    jobs = worker.fetch_queued()
    assert [worker.prop(item, "Job") for item in jobs] == ["New manual job", "Verified job"]


def test_terminal_processing_stages_are_not_requeued(monkeypatch):
    monkeypatch.setattr(
        worker,
        "notion_request",
        lambda *args, **kwargs: {
            "results": [
                page("Ready", "Ready to Apply"),
                page("Applied", "Applied"),
                page("Blocked", "Blocked"),
                page("New", "Discovered"),
            ],
            "has_more": False,
        },
    )
    jobs = worker.fetch_queued()
    assert [worker.prop(item, "Job") for item in jobs] == ["New"]


def test_data_source_query_endpoint_and_pagination(monkeypatch):
    calls = []
    responses = iter(
        [
            {"results": [page("First", "Ready to Apply")], "has_more": True, "next_cursor": "cursor-1"},
            {"results": [page("Second", "Discovered")], "has_more": False, "next_cursor": None},
        ]
    )

    def fake_request(method, path, body=None):
        calls.append((method, path, body))
        return next(responses)

    monkeypatch.setattr(worker, "notion_request", fake_request)
    monkeypatch.setattr(worker, "MAX_JOBS", 1)
    jobs = worker.fetch_queued()
    assert len(calls) == 2
    assert calls[0][0] == "POST"
    assert calls[0][1].endswith("/data_sources/8374c380f14841aba77feb35de20f2db/query")
    assert calls[1][2]["start_cursor"] == "cursor-1"
    assert [worker.prop(item, "Job") for item in jobs] == ["Second"]


def test_retry_after_is_honoured_and_bounded(monkeypatch):
    sleeps = []
    monkeypatch.setattr(worker.time, "sleep", lambda seconds: sleeps.append(seconds))
    worker._sleep_for_retry(4, "120")
    assert sleeps == [60.0]


def test_process_failure_is_isolated(monkeypatch):
    updates = []

    def fail_pipeline(*args, **kwargs):
        raise RuntimeError("synthetic pipeline failure")

    monkeypatch.setattr(worker, "CareerPipeline", fail_pipeline)
    monkeypatch.setattr(worker, "update_page", lambda page_id, values: updates.append((page_id, values)))
    ok, message = worker.process(
        page("Broken", "Discovered", "Verified Active", jd="A real job description"),
        {"candidate": {"professional_summary": "x"}},
    )
    assert ok is False
    assert "synthetic pipeline failure" in message
    assert updates[-1][1]["Processing Stage"] == "Blocked"
    assert updates[-1][1]["Resume Status"] == "Failed"
