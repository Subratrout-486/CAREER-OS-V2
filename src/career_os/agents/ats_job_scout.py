from __future__ import annotations

from collections.abc import Iterable

from career_os.agents.job_intake import JobIntakePipeline
from career_os.integrations.ats import (
    AshbyAdapter,
    GreenhouseAdapter,
    LeverAdapter,
    RawATSJob,
    RipplingAdapter,
    WorkdayAdapter,
)
from career_os.models.job import JobRecord


class ATSJobScout:
    """Run a public ATS adapter and feed its records into the canonical intake pipeline."""

    def __init__(self, intake: JobIntakePipeline | None = None) -> None:
        self.intake = intake or JobIntakePipeline()

    @staticmethod
    def _mapping(job: RawATSJob) -> dict[str, object]:
        return {
            "provider": job.provider,
            "company": job.company,
            "title": job.title,
            "location": job.location,
            "description": job.description,
            "job_url": job.job_url,
            "posted_at": job.posted_at,
            "external_id": job.external_id,
        }

    def ingest(self, jobs: Iterable[RawATSJob]) -> list[JobRecord]:
        return self.intake.ingest(self._mapping(job) for job in jobs)

    def greenhouse(self, slug: str) -> list[JobRecord]:
        return self.ingest(GreenhouseAdapter().fetch(slug))

    def lever(self, slug: str) -> list[JobRecord]:
        return self.ingest(LeverAdapter().fetch(slug))

    def ashby(self, slug: str) -> list[JobRecord]:
        return self.ingest(AshbyAdapter().fetch(slug))

    def workday(self, board_url: str, *, max_jobs: int = 100) -> list[JobRecord]:
        return self.ingest(WorkdayAdapter().fetch(board_url, max_jobs=max_jobs))

    def rippling(self, slug: str) -> list[JobRecord]:
        return self.ingest(RipplingAdapter().fetch(slug))
