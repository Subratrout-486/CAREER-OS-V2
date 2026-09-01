#!/usr/bin/env python3
"""Finalize only jobs processed by the current worker pass."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import notion_job_worker

import notion_resume_finalize


REPORT = notion_job_worker.ROOT / ".career-os" / "notion-worker-report.json"


def fetch_processed() -> list[dict]:
    if not REPORT.exists():
        raise RuntimeError(f"processing report not found: {REPORT}")
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    pages = []
    for row in data.get("results", []):
        if not row.get("ok") or not row.get("job_id"):
            continue
        pages.append(notion_job_worker.notion_request("GET", f"/pages/{row['job_id']}"))
    return pages


# Finalization must consume the exact successful processing IDs, not re-query
# the queue, because the queue can change between the two stages.
notion_resume_finalize.fetch_queued = fetch_processed


if __name__ == "__main__":
    rc = notion_resume_finalize.main()
    report = notion_job_worker.ROOT / ".career-os" / "resume-finalize-report.json"
    data = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
    failures = [row for row in data.get("results", []) if not row.get("ok")]
    if failures:
        print(f"Finalization failures: {len(failures)}")
        sys.exit(1)
    sys.exit(rc)
