from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "notion_resume_finalize_safety",
    SCRIPTS / "notion_resume_finalize.py",
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_internal_career_os_job_is_blocked(monkeypatch) -> None:
    updates = []
    monkeypatch.setattr(module, "update_page", lambda page_id, values: updates.append((page_id, values)))
    page = {
        "id": "page-1",
        "properties": {
            "Job": {"type": "title", "title": [{"plain_text": "Career OS V2 E2E Automation Test"}]},
            "Company": {"type": "rich_text", "rich_text": [{"plain_text": "Career OS"}]},
            "JD": {"type": "rich_text", "rich_text": [{"plain_text": "synthetic test job"}]},
        },
    }

    ok, message = module.finalize(page, {"candidate": {"name": "Subrat Rout"}})

    assert ok is False
    assert "blocked internal test job" in message
    assert updates[0][1]["Processing Stage"] == "Blocked"
    assert updates[0][1]["Status"] == "Rejected"


def test_finalizer_uses_worker_compatible_sanitized_run_id(monkeypatch, tmp_path: Path) -> None:
    checkpoint = tmp_path / "runs" / "notion-accenture-application-support-engineer-python-atci-5450450-s2011639-page1.json"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("not a completed checkpoint", encoding="utf-8")

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "load_completed_result", lambda path: (_ for _ in ()).throw(FileNotFoundError(str(path))))

    page = {
        "id": "page-1",
        "properties": {
            "Job": {"type": "title", "title": [{"plain_text": "Application Support Engineer — Python (ATCI-5450450-S2011639)"}]},
            "Company": {"type": "rich_text", "rich_text": [{"plain_text": "Accenture"}]},
            "JD": {"type": "rich_text", "rich_text": [{"plain_text": "real job description"}]},
        },
    }

    try:
        module.finalize(page, {"candidate": {"name": "Subrat Rout"}})
    except FileNotFoundError as exc:
        assert "notion-accenture-application-support-engineer-python-atci-5450450-s2011639-page1" in str(exc)
    else:
        raise AssertionError("Expected checkpoint lookup to use the worker-compatible sanitized run id")
