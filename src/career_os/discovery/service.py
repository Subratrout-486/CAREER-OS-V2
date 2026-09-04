"""Operational job discovery service.

Composes public ATS feeds, public job-board APIs, and a Scrapling-based scraper
into a single normalized flow. Every source's jobs are normalized through the
existing deterministic intake pipeline, deduplicated, and scored for freshness
and source reliability. Any single source failing never aborts the others.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from career_os.agents.job_intake import JobIntakePipeline
from career_os.integrations.ats import RawATSJob
from career_os.integrations.public_job_apis import PublicJob
from career_os.models.job import JobRecord, JobStatus

_SOURCE_RELIABILITY = {
    "greenhouse": 1.0,
    "lever": 1.0,
    "ashby": 1.0,
    "workday": 1.0,
    "rippling": 1.0,
    "smartrecruiters": 0.95,
    "teamtailor": 0.9,
    "adzuna": 0.85,
    "arbeitnow": 0.85,
    "scrapling": 0.75,
}

_MAX_AGE_DAYS = 30


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _freshness_score(posted_at: datetime | None, now: datetime | None = None) -> float:
    now = now or _utcnow()
    if posted_at is None:
        return 0.5
    age = now - posted_at
    if age.days < 0:
        return 0.5
    if age.days == 0:
        return 1.0
    if age.days >= _MAX_AGE_DAYS:
        return 0.0
    return round(max(0.0, 1.0 - age.days / _MAX_AGE_DAYS), 2)


def _reliability_score(source: str) -> float:
    return _SOURCE_RELIABILITY.get(source.casefold().strip(), 0.5)


@dataclass(frozen=True)
class DiscoveryItem:
    source: str
    raw: Any

    def to_intake(self) -> dict[str, Any]:
        if isinstance(self.raw, RawATSJob):
            return {
                "company": self.raw.company,
                "title": self.raw.title,
                "location": self.raw.location,
                "description": self.raw.description,
                "url": self.raw.job_url,
                "source": self.raw.provider,
                "external_id": self.raw.external_id,
                "posted_at": self.raw.posted_at.isoformat() if self.raw.posted_at else None,
            }
        if isinstance(self.raw, PublicJob):
            full = {
                "company": self.raw.company,
                "title": self.raw.title,
                "location": self.raw.location,
                "description": self.raw.description,
                "url": self.raw.job_url,
                "source": self.raw.provider,
                "external_id": self.raw.external_id,
                "posted_at": self.raw.posted_at.isoformat() if self.raw.posted_at else None,
                "remote": self.raw.remote,
                "salary_min": self.raw.salary_min,
                "salary_max": self.raw.salary_max,
                "salary_currency": self.raw.salary_currency,
                "salary_is_predicted": self.raw.salary_is_predicted,
                "employment_type": self.raw.employment_type,
                "tags": list(self.raw.tags),
            }
            return full
        if isinstance(self.raw, dict):
            return self.raw
        return {}


@dataclass
class DiscoveredJob:
    record: JobRecord
    freshness: float
    reliability: float
    priority: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "company": self.record.company,
            "title": self.record.title,
            "location": self.record.location,
            "source": self.record.source,
            "source_url": str(self.record.source_url),
            "source_type": self.record.source_type.value,
            "job_id": str(self.record.job_id),
            "external_id": self.record.external_id,
            "posted_at": self.record.posted_at.isoformat() if self.record.posted_at else None,
            "remote": self.record.remote,
            "freshness": self.freshness,
            "reliability": self.reliability,
            "priority": self.priority,
            "status": self.record.status.value,
            "duplicate_of": str(self.record.duplicate_of) if self.record.duplicate_of else None,
        }


@dataclass
class DiscoveryResult:
    jobs: list[DiscoveredJob] = field(default_factory=list)
    source_errors: dict[str, str] = field(default_factory=dict)

    @property
    def unique_jobs(self) -> list[DiscoveredJob]:
        return [job for job in self.jobs if job.record.status is not JobStatus.DUPLICATE]


class JobDiscoveryService:
    """Normalize, dedup and rank jobs from multiple discovery sources."""

    def __init__(
        self,
        *,
        intake: JobIntakePipeline | None = None,
        now: datetime | None = None,
    ) -> None:
        self.intake = intake or JobIntakePipeline()
        self.now = now

    def ingest(self, items: list[DiscoveryItem]) -> DiscoveryResult:
        result = DiscoveryResult()
        # Normalize every item into a job + scoring metadata, isolating errors.
        entries: list[DiscoveredJob] = []
        for item in items:
            try:
                raw = item.to_intake()
                record = self.intake.normalize(raw)
                freshness = _freshness_score(record.posted_at, self.now)
                reliability = _reliability_score(item.source)
                priority = round(0.6 * freshness + 0.4 * reliability, 3)
                entries.append(DiscoveredJob(record, freshness, reliability, priority))
            except Exception as exc:  # noqa: BLE001 - one bad source must not abort the batch
                result.source_errors.setdefault(item.source, str(exc))

        # Dedup within the batch by canonical key and content fingerprint.
        seen_keys: set[str] = set()
        seen_fingerprints: set[str] = set()
        for job in entries:
            key = job.record.canonical_key
            fingerprint = job.record.content_fingerprint or ""
            duplicate = key in seen_keys or (fingerprint and fingerprint in seen_fingerprints)
            if duplicate:
                job.record.status = JobStatus.DUPLICATE
            else:
                seen_keys.add(key)
                if fingerprint:
                    seen_fingerprints.add(fingerprint)
            result.jobs.append(job)

        result.jobs.sort(key=lambda job: job.priority, reverse=True)
        return result

    def rank(self, jobs: list[DiscoveredJob]) -> list[DiscoveredJob]:
        return sorted(jobs, key=lambda job: job.priority, reverse=True)

    def deduplicate(self, jobs: list[DiscoveredJob]) -> list[DiscoveredJob]:
        records = self.intake.ingest([job.to_dict() for job in jobs])
        by_job_id = {str(job.record.job_id): job for job in jobs}
        seen: set[str] = set()
        result: list[DiscoveredJob] = []
        for record in records:
            if record.status is JobStatus.DUPLICATE:
                continue
            key = str(record.job_id)
            if key in by_job_id and key not in seen:
                seen.add(key)
                result.append(by_job_id[key])
        return result
