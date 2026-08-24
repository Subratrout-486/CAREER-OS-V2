from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "notion_job_worker_runtime.py"
spec = importlib.util.spec_from_file_location("notion_job_worker_runtime", MODULE_PATH)
assert spec is not None and spec.loader is not None
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def test_live_status_schema_uses_select(monkeypatch):
    captured = []
    monkeypatch.setattr(
        runtime.worker,
        "notion_request",
        lambda method, path, body=None: captured.append((method, path, body)) or {},
    )

    runtime.update_page(
        "page-1",
        {"Status": "Analyzing", "Processing Stage": "Analyzing", "Resume Status": "Generating"},
    )

    properties = captured[0][2]["properties"]
    assert properties["Status"] == {"select": {"name": "Analyzing"}}
    assert properties["Processing Stage"] == {"select": {"name": "Analyzing"}}
    assert properties["Resume Status"] == {"select": {"name": "Generating"}}
