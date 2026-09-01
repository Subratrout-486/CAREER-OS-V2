#!/usr/bin/env python3
"""Finalize the jobs processed by the current worker pass."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import notion_job_worker

# The processing worker advances jobs to Recruiter Review. Finalization must
# consume that exact state, not the still-queued records behind the page limit.
notion_job_worker.QUEUE_STAGES = {"Recruiter Review"}

import notion_resume_finalize


if __name__ == "__main__":
    rc = notion_resume_finalize.main()
    report = Path(".career-os/resume-finalize-report.json")
    data = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
    failures = [row for row in data.get("results", []) if not row.get("ok")]
    if failures:
        print(f"Finalization failures: {len(failures)}")
        sys.exit(1)
    sys.exit(rc)
