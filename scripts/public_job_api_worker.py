#!/usr/bin/env python3
"""Discover recent public jobs and queue them in the live Notion Jobs database."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from career_os.agents.public_job_scout import PublicJobScout
from career_os.agents.source_runner import SourceRunner
from career_os.integrations.public_job_apis import AdzunaAdapter, ArbeitnowAdapter, OpenSkillsAdapter
from career_os.models.job import JobRecord

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".career-os" / "public-job-api-report.json"
DEFAULT_DATA_SOURCE_ID = "8374c380-f148-41ab-a77f-eb35de20f2db"
NOTION_VERSION = os.environ.get("NOTION_VERSION", "2026-03-11")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().casefold() in {"1", "true", "yes", "y"}


def _notion_request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        raise RuntimeError("NOTION_TOKEN is not configured")
    request = Request(
        "https://api.notion.com/v1" + path,
        data=None if body is None else json.dumps(body).encode("utf-8"),
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Career-OS-V2/1.0",
        },
    )
    for attempt in range(4):
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError):
            if attempt == 3:
                raise
            time.sleep(min(8, 2**attempt))
    raise RuntimeError("Notion request failed")


def _prop(page: dict[str, Any], name: str) -> str:
    value = page.get("properties", {}).get(name, {})
    kind = value.get("type")
    data = value.get(kind, {})
    if kind in {"title", "rich_text"}:
        return "".join(x.get("plain_text", "") for x in data).strip()
    if kind == "url":
        return data or ""
    if kind in {"select", "status"}:
        return (data or {}).get("name", "")
    return ""


def _existing_urls() -> set[str]:
    data_source_id = os.environ.get("NOTION_DATA_SOURCE_ID", DEFAULT_DATA_SOURCE_ID).replace("-", "")
    response = _notion_request("POST", f"/data_sources/{data_source_id}/query", {"page_size": 100})
    return {_prop(page, "Job URL") for page in response.get("results", []) if _prop(page, "Job URL")}


def _create_notion_job(job: JobRecord) -> str:
    data_source_id = os.environ.get("NOTION_DATA_SOURCE_ID", DEFAULT_DATA_SOURCE_ID).replace("-", "")
    properties = {
        "Job": {"title": [{"type": "text", "text": {"content": job.title[:2000]}}]},
        "Company": {"rich_text": [{"type": "text", "text": {"content": job.company[:1900]}}]},
        "JD": {"rich_text": [{"type": "text", "text": {"content": (job.description or "")[:1900]}}]},
        "Job URL": {"url": job.source_url or None},
        "Location": {"rich_text": [{"type": "text", "text": {"content": (job.location or "")[:1900]}}]},
        "Source": {"rich_text": [{"type": "text", "text": {"content": (job.source or "Public API")[:1900]}}]},
        "Status": {"select": {"name": "Verified Active"}},
        "Processing Stage": {"select": {"name": "Discovered"}},
        "Resume Status": {"select": {"name": "Not Started"}},
    }
    response = _notion_request("POST", "/pages", {
        "parent": {"type": "data_source_id", "data_source_id": data_source_id},
        "properties": properties,
    })
    return str(response.get("id", ""))


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
            country=os.getenv("CAREER_OS_ADZUNA_COUNTRY", "in"), query=q,
            location=os.getenv("CAREER_OS_ADZUNA_LOCATION"), pages=_int("CAREER_OS_ADZUNA_PAGES", 1),
            results_per_page=_int("CAREER_OS_ADZUNA_RESULTS_PER_PAGE", 20),
        ))))
    else:
        skipped.append("adzuna:not_configured")

    arbeitnow_query = os.getenv("CAREER_OS_ARBEITNOW_QUERY") or os.getenv("CAREER_OS_PUBLIC_JOB_QUERY")
    if arbeitnow_query:
        adapter = ArbeitnowAdapter()
        tasks.append(("arbeitnow", "public-job-search", lambda a=adapter, q=arbeitnow_query: scout.ingest(a.fetch(
            query=q, location=os.getenv("CAREER_OS_ARBEITNOW_LOCATION"),
            remote_only=_bool("CAREER_OS_ARBEITNOW_REMOTE_ONLY"), pages=_int("CAREER_OS_ARBEITNOW_PAGES", 1),
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
    except Exception as exc:
        job.risk_signals.append(f"OPEN_SKILLS_ENRICHMENT_FAILED:{type(exc).__name__}")
    return job


def main() -> int:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tasks, skipped = _source_tasks()
    records, diagnostics = SourceRunner().run(tasks)
    max_jobs = max(1, _int("CAREER_OS_PUBLIC_API_MAX_JOBS", 20))
    max_age_days = max(0, _int("CAREER_OS_PUBLIC_API_MAX_AGE_DAYS", 2))
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    existing_urls = _existing_urls() if os.getenv("NOTION_TOKEN") else set()
    discovered: list[dict[str, Any]] = []
    created = duplicates = stale = failures = 0

    for job in records:
        if job.status.value == "DUPLICATE":
            duplicates += 1
            continue
        if job.posted_at and job.posted_at.astimezone(timezone.utc) < cutoff:
            stale += 1
            continue
        if job.source_url in existing_urls:
            duplicates += 1
            continue
        job = _enrich(job)
        try:
            page_id = _create_notion_job(job)
            existing_urls.add(job.source_url)
            created += 1
            discovered.append({"job_id": str(job.job_id), "notion_page_id": page_id, "title": job.title, "company": job.company, "status": "queued"})
        except Exception as exc:
            failures += 1
            discovered.append({"job_id": str(job.job_id), "title": job.title, "company": job.company, "status": "not_queued", "error": f"{type(exc).__name__}: {exc}"})
        if created >= max_jobs:
            break

    payload = {
        "sources": [diagnostic.model_dump(mode="json") for diagnostic in diagnostics],
        "skipped": skipped, "fetched_records": len(records), "created_notion_jobs": created,
        "duplicates": duplicates, "stale_filtered": stale, "queue_failures": failures, "discovered": discovered,
    }
    REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
