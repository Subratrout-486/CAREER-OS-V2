#!/usr/bin/env python3
"""Fetch configured public job APIs and feed jobs into the normal CareerOS pipeline.

Provider and job failures are isolated. A disabled/unconfigured provider is skipped,
and one bad job cannot stop the remaining jobs from being processed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from career_os.agents.public_job_scout import PublicJobScout
from career_os.automation.job_processor import AutomaticJobProcessor, JobProcessingRequest
from career_os.agents.source_runner import SourceRunner
from career_os.integrations.public_job_apis import AdzunaAdapter, ArbeitnowAdapter, OpenSkillsAdapter
from career_os.models.job import JobRecord

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".career-os" / "public-job-api-report.json"


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().casefold() in {"1", "true", "yes", "y"}


def _source_tasks() -> tuple[list[tuple[str, str, object]], list[str]]:
    scout = PublicJobScout()
    tasks: list[tuple[str, str, object]] = []
    skipped: list[str] = []

    adzuna_id = os.getenv("ADZUNA_APP_ID")
    adzuna_key = os.getenv("ADZUNA_APP_KEY")
    adzuna_query = os.getenv("CAREER_OS_ADZUNA_QUERY") or os.getenv("CAREER_OS_PUBLIC_JOB_QUERY")
    if adzuna_id and adzuna_key and adzuna_query:
        adapter = AdzunaAdapter(adzuna_id, adzuna_key)
        tasks.append(("adzuna", "public-job-search", lambda a=adapter, q=adzuna_query: scout.ingest(a.fetch(
            country=os.getenv("CAREER_OS_ADZUNA_COUNTRY", "in"),
            query=q,
            location=os.getenv("CAREER_OS_ADZUNA_LOCATION"),
            pages=_int("CAREER_OS_ADZUNA_PAGES", 1),
            results_per_page=_int("CAREER_OS_ADZUNA_RESULTS_PER_PAGE", 20),
        ))))
    else:
        skipped.append("adzuna:not_configured")

    arbeitnow_query = os.getenv("CAREER_OS_ARBEITNOW_QUERY") or os.getenv("CAREER_OS_PUBLIC_JOB_QUERY")
    if arbeitnow_query:
        adapter = ArbeitnowAdapter()
        tasks.append(("arbeitnow", "public-job-search", lambda a=adapter, q=arbeitnow_query: scout.ingest(a.fetch(
            query=q,
            location=os.getenv("CAREER_OS_ARBEITNOW_LOCATION"),
            remote_only=_bool("CAREER_OS_ARBEITNOW_REMOTE_ONLY"),
            pages=_int("CAREER_OS_ARBEITNOW_PAGES", 1),
        ))))
    else:
        skipped.append("arbeitnow:not_configured")
    return tasks, skipped


def _enrich(job: JobRecord) -> JobRecord:
    if not _bool("CAREER_OS_OPEN_SKILLS_ENABLED"):
        return job
    try:
        adapter = OpenSkillsAdapter(
            base_url=os.getenv("CAREER_OS_OPEN_SKILLS_BASE_URL", OpenSkillsAdapter.default_base_url),
            allow_insecure_http=_bool("CAREER_OS_OPEN_SKILLS_ALLOW_HTTP"),
        )
        result = adapter.enrich_title(job.title, max_skills=_int("CAREER_OS_OPEN_SKILLS_MAX_SKILLS", 20))
        job.normalized_title = result.canonical_title
        job.normalized_skills = list(result.skills)
    except Exception as exc:  # enrichment is non-critical and must never block job processing
        job.risk_signals.append(f"OPEN_SKILLS_ENRICHMENT_FAILED:{type(exc).__name__}")
    return job


def main() -> int:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tasks, skipped = _source_tasks()
    records, diagnostics = SourceRunner().run(tasks)

    processed: list[dict[str, object]] = []
    processor = AutomaticJobProcessor(
        checkpoint_root=ROOT / ".career-os" / "automatic_runs" / "public-api"
    )
    max_jobs = max(1, _int("CAREER_OS_PUBLIC_API_MAX_JOBS", 20))
    for job in records:
        if job.status.value == "DUPLICATE":
            continue
        job = _enrich(job)
        try:
            result = processor.process(JobProcessingRequest(job=job.model_dump(mode="json")))
            processed.append({"job_id": str(job.job_id), "status": "processed", "application_ready": result.application_ready})
        except Exception as exc:
            processed.append({"job_id": str(job.job_id), "status": "blocked_or_failed", "error": f"{type(exc).__name__}: {exc}"})
        if len(processed) >= max_jobs:
            break

    payload = {
        "sources": [diagnostic.model_dump(mode="json") for diagnostic in diagnostics],
        "skipped": skipped,
        "fetched_records": len(records),
        "processed_attempts": len(processed),
        "processed": processed,
    }
    REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
