from __future__ import annotations

from dataclasses import dataclass

from career_os.integrations.ats import RawATSJob, WorkdayAdapter
from career_os.integrations.provider_registry import ATSProviderRegistry


@dataclass(frozen=True)
class DiscoveryResult:
    careers_url: str
    provider: str | None
    jobs: tuple[RawATSJob, ...]


class ATSDiscoveryService:
    """Resolve a public careers URL, scan its provider, and return normalized ATS jobs."""

    def __init__(self, registry: ATSProviderRegistry | None = None) -> None:
        self.registry = registry or ATSProviderRegistry()

    def scan(self, careers_url: str, *, max_jobs: int = 100) -> DiscoveryResult:
        match = self.registry.resolve(careers_url)
        if match is None:
            return DiscoveryResult(careers_url, None, ())

        if match.provider == "workday":
            jobs = match.adapter.fetch(careers_url, max_jobs=max_jobs)
        elif match.provider in {"teamtailor", "smartrecruiters"}:
            jobs = match.adapter.fetch(match.identifier)
        else:
            jobs = match.adapter.fetch(match.identifier)
        return DiscoveryResult(careers_url, match.provider, tuple(jobs[:max_jobs]))

    @staticmethod
    def to_intake_records(result: DiscoveryResult) -> list[dict[str, object]]:
        return [
            {
                "company": job.company,
                "title": job.title,
                "location": job.location,
                "source_url": job.job_url,
                "source": job.provider,
                "description": job.description,
                "posted_at": job.posted_at,
            }
            for job in result.jobs
        ]
