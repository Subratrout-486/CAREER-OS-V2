from __future__ import annotations

from collections.abc import Iterable

from career_os.agents.job_intake import JobIntakePipeline
from career_os.integrations.public_job_apis import PublicJob
from career_os.models.job import JobRecord


class PublicJobScout:
    """Convert public job API records into the canonical CareerOS intake flow."""

    def __init__(self, intake: JobIntakePipeline | None = None) -> None:
        self.intake = intake or JobIntakePipeline()

    def ingest(self, jobs: Iterable[PublicJob]) -> list[JobRecord]:
        return self.intake.ingest(job.as_mapping() for job in jobs)
