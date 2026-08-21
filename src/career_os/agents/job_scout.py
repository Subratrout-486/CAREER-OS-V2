from __future__ import annotations

from collections.abc import Iterable

from career_os.models.job import JobRecord, JobStatus, canonical_job_key


class JobScout:
    """Deterministic first-stage intake: identity, duplicate checks and verification state."""

    name = "job_scout"

    def build_record(
        self,
        *,
        company: str,
        title: str,
        location: str | None,
        source_url: str,
        source: str,
        description: str | None = None,
    ) -> JobRecord:
        return JobRecord(
            company=company.strip(),
            title=title.strip(),
            location=location.strip() if location else None,
            source_url=source_url,
            source=source.strip(),
            canonical_key=canonical_job_key(company, title, location, source_url),
            description=description,
        )

    def deduplicate(self, jobs: Iterable[JobRecord]) -> list[JobRecord]:
        seen: dict[str, JobRecord] = {}
        result: list[JobRecord] = []
        for job in jobs:
            existing = seen.get(job.canonical_key)
            if existing is not None:
                job.status = JobStatus.DUPLICATE
                job.duplicate_of = existing.job_id
            else:
                seen[job.canonical_key] = job
            result.append(job)
        return result
