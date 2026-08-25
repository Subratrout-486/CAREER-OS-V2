from __future__ import annotations

from collections.abc import Iterable
from difflib import SequenceMatcher

from career_os.models.job import JobRecord, JobStatus, SourceType, canonical_job_key, content_fingerprint


_ATS_HOSTS = {
    "boards.greenhouse.io": SourceType.ATS,
    "job-boards.greenhouse.io": SourceType.ATS,
    "jobs.lever.co": SourceType.ATS,
    "jobs.ashbyhq.com": SourceType.ATS,
    "jobs.smartrecruiters.com": SourceType.ATS,
    "myworkdayjobs.com": SourceType.ATS,
}

_JOB_BOARD_SOURCES = {"adzuna", "arbeitnow"}


def infer_source_type(source: str, url: str) -> SourceType:
    source_lower = source.casefold()
    if source_lower in _JOB_BOARD_SOURCES:
        return SourceType.JOB_BOARD
    if "official" in source_lower or "career" in source_lower:
        return SourceType.OFFICIAL_CAREER_PAGE
    host = url.casefold().split("/", 3)[2] if "://" in url else ""
    for known_host, source_type in _ATS_HOSTS.items():
        if host == known_host or host.endswith("." + known_host):
            return source_type
    if any(token in source_lower for token in ("linkedin", "indeed", "glassdoor", "ziprecruiter", "board")):
        return SourceType.JOB_BOARD
    if "search" in source_lower or "google" in source_lower:
        return SourceType.SEARCH_RESULT
    if "user" in source_lower or "manual" in source_lower:
        return SourceType.USER_SUBMITTED
    return SourceType.UNKNOWN


def _norm(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _fuzzy_duplicate(a: JobRecord, b: JobRecord) -> bool:
    if _norm(a.company) != _norm(b.company) or _norm(a.location) != _norm(b.location):
        return False
    title_similarity = SequenceMatcher(None, _norm(a.title), _norm(b.title)).ratio()
    if title_similarity < 0.94:
        return False
    if not a.description or not b.description:
        return title_similarity >= 0.98
    description_similarity = SequenceMatcher(None, _norm(a.description), _norm(b.description)).ratio()
    return description_similarity >= 0.92


class JobScout:
    """Deterministic first-stage intake: identity, source classification and dedupe."""

    name = "job_scout"

    def build_record(self, *, company: str, title: str, location: str | None,
                     source_url: str, source: str, description: str | None = None) -> JobRecord:
        source_type = infer_source_type(source, source_url)
        record = JobRecord(
            company=company.strip(), title=title.strip(), location=location.strip() if location else None,
            source_url=source_url, source=source.strip(), source_type=source_type,
            canonical_key=canonical_job_key(company, title, location, source_url),
            content_fingerprint=content_fingerprint(company, title, location, description),
            description=description,
        )
        if source_type is SourceType.SEARCH_RESULT:
            record.risk_signals.append("SEARCH_RESULT_NEEDS_ORIGIN_VERIFICATION")
        if source_type is SourceType.JOB_BOARD:
            record.risk_signals.append("JOB_BOARD_NEEDS_ORIGIN_VERIFICATION")
        return record

    def deduplicate(self, jobs: Iterable[JobRecord]) -> list[JobRecord]:
        result: list[JobRecord] = []
        by_key: dict[str, JobRecord] = {}
        by_content: dict[str, JobRecord] = {}
        for job in jobs:
            existing = by_key.get(job.canonical_key)
            if existing is None and job.content_fingerprint:
                existing = by_content.get(job.content_fingerprint)
            if existing is None:
                for candidate in result:
                    if candidate.status is not JobStatus.DUPLICATE and _fuzzy_duplicate(candidate, job):
                        existing = candidate
                        break
            if existing is not None:
                job.status = JobStatus.DUPLICATE
                job.duplicate_of = existing.job_id
            else:
                by_key[job.canonical_key] = job
                if job.content_fingerprint:
                    by_content[job.content_fingerprint] = job
            result.append(job)
        return result
