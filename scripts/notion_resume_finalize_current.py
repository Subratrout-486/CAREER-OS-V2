#!/usr/bin/env python3
"""Finalize only the jobs successfully selected by the current worker pass."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import notion_job_worker
import notion_resume_finalize

REPORT = Path(".career-os/notion-worker-report.json")


def fetch_processed() -> list[dict[str, object]]:
    """Rehydrate exactly the successful page IDs from this processing pass.

    The processing worker's report is the handoff boundary. Re-querying the
    mutable Notion queue here can select unrelated/manual Recruiter Review
    records when earlier jobs were blocked or advanced during the same pass.
    """
    if not REPORT.exists():
        raise RuntimeError("processing report is missing; refusing to finalize an untracked queue")
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    rows = payload.get("results") or []
    page_ids = [str(row.get("job_id")) for row in rows if row.get("ok") and row.get("job_id")]
    if not page_ids:
        return []
    pages: list[dict[str, object]] = []
    for page_id in page_ids:
        pages.append(notion_job_worker.notion_request("GET", f"/pages/{page_id}"))
    return pages


# The finalizer imported fetch_queued directly, so patch its module-level
# reference to consume this pass's durable processing handoff.
notion_resume_finalize.fetch_queued = fetch_processed


if __name__ == "__main__":
    rc = notion_resume_finalize.main()
    report = Path(".career-os/resume-finalize-report.json")
    data = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
    failures = [row for row in data.get("results", []) if not row.get("ok")]
    if failures:
        print(f"Finalization failures: {len(failures)}")
        sys.exit(1)
    sys.exit(rc)
