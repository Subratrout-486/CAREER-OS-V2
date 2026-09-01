from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "notion_application_worker.py"
spec = importlib.util.spec_from_file_location("notion_application_worker", MODULE_PATH)
assert spec is not None and spec.loader is not None
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def test_query_omits_optional_filter_when_unfiltered(monkeypatch):
    calls = []

    def fake_request(method, path, body=None):
        calls.append((method, path, body))
        return {"results": [{"id": "job-1"}]}

    monkeypatch.setattr(worker.notion_job_worker, "notion_request", fake_request)
    rows = worker._query("1111-2222", "")

    assert rows == [{"id": "job-1"}]
    assert calls == [("POST", "/data_sources/11112222/query", {"page_size": 100})]
    assert "filter" not in calls[0][2]
