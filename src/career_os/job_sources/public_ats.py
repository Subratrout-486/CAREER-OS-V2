from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.parse import quote
from urllib.request import Request, urlopen

from career_os.agents.job_intake import JobIntakePipeline
from career_os.models.job import JobRecord


@dataclass(frozen=True)
class ATSJobSource:
    """Public, credential-free ATS board definition."""

    provider: str
    slug: str

    def endpoint(self) -> str:
        slug = quote(self.slug.strip(), safe="-")
        if self.provider == "greenhouse":
            return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        if self.provider == "ashby":
            return f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
        if self.provider == "lever":
            return f"https://api.lever.co/v0/postings/{slug}?mode=json"
        raise ValueError(f"unsupported public ATS provider: {self.provider}")


def _fetch_json(url: str, timeout: float = 15.0) -> object:
    request = Request(url, headers={"User-Agent": "CareerOS-V2/0.1 (+public-job-discovery)"})
    with urlopen(request, timeout=timeout) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"job source returned HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def _greenhouse_jobs(payload: object, source: ATSJobSource) -> list[dict[str, object]]:
    rows = payload.get("jobs", []) if isinstance(payload, dict) else []
    jobs: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        location = row.get("location")
        location_name = location.get("name") if isinstance(location, dict) else location
        jobs.append({
            "company": source.slug,
            "title": row.get("title", ""),
            "location": location_name,
            "url": row.get("absolute_url", ""),
            "source": "greenhouse",
            "description": row.get("content"),
            "posted_at": row.get("updated_at"),
        })
    return jobs


def _ashby_jobs(payload: object, source: ATSJobSource) -> list[dict[str, object]]:
    rows = payload.get("jobPostings", []) if isinstance(payload, dict) else []
    jobs: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        jobs.append({
            "company": source.slug,
            "title": row.get("title", ""),
            "location": ", ".join(row.get("locationNames", []) or []),
            "url": row.get("jobUrl") or row.get("applyUrl", ""),
            "source": "ashby",
            "description": row.get("descriptionPlain") or row.get("descriptionHtml"),
            "posted_at": row.get("publishedAt"),
        })
    return jobs


def _lever_jobs(payload: object, source: ATSJobSource) -> list[dict[str, object]]:
    rows = payload if isinstance(payload, list) else []
    jobs: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        categories = row.get("categories") or {}
        location = categories.get("location") if isinstance(categories, dict) else None
        description = row.get("descriptionPlain") or row.get("description")
        jobs.append({
            "company": source.slug,
            "title": row.get("text", ""),
            "location": location,
            "url": row.get("hostedUrl") or row.get("applyUrl", ""),
            "source": "lever",
            "description": description,
            "posted_at": row.get("createdAt"),
        })
    return jobs


def discover_ats_jobs(source: ATSJobSource, *, timeout: float = 15.0) -> list[JobRecord]:
    """Fetch one public ATS board and return canonical, deduplicated JobRecords.

    This function only discovers and normalizes jobs. It never evaluates a job,
    invents candidate facts, or submits an application.
    """
    payload = _fetch_json(source.endpoint(), timeout=timeout)
    if source.provider == "greenhouse":
        raw_jobs = _greenhouse_jobs(payload, source)
    elif source.provider == "ashby":
        raw_jobs = _ashby_jobs(payload, source)
    elif source.provider == "lever":
        raw_jobs = _lever_jobs(payload, source)
    else:
        raise ValueError(f"unsupported public ATS provider: {source.provider}")
    return JobIntakePipeline().ingest(raw_jobs)
