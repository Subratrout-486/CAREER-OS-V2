"""Adapter for feeding external AI job-search results into Career OS.

Accepts normalized job dictionaries, deduplicates by canonical URL, and delegates
persistence to the existing Notion job worker. This deliberately contains no new
scoring or resume logic: those remain owned by Career OS.
"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def canonical_job_url(url: str) -> str:
    p = urlsplit((url or "").strip())
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", ""))


def normalize_jobs(jobs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for job in jobs:
        url = canonical_job_url(str(job.get("job_url") or job.get("url") or ""))
        title = str(job.get("title") or "").strip()
        company = str(job.get("company") or "").strip()
        if not url or not title or not company or url in seen:
            continue
        seen.add(url)
        result.append({**job, "job_url": url, "title": title, "company": company})
    return result


def build_processing_batch(jobs: list[dict], max_jobs: int = 100) -> list[dict]:
    """Return bounded, normalized jobs for the existing Career OS processors."""
    if max_jobs < 1:
        raise ValueError("max_jobs must be positive")
    return normalize_jobs(jobs)[:max_jobs]
