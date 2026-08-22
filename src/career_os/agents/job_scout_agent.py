from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from career_os.agents.ats_job_scout import ATSJobScout
from career_os.agents.job_scout import JobScout
from career_os.agents.skill_agent import SkillBackedAgent
from career_os.integrations.ats import RawATSJob
from career_os.models.job import JobRecord


class JobScoutAgent(SkillBackedAgent):
    """Skill-backed Job Scout department.

    The Agent Skill defines the procedure and guardrails. Existing deterministic
    ATS adapters, normalization, deduplication, and verification remain the
    executable implementation.
    """

    skill_name = "job-scout"

    def __init__(self, *, skills_root: Path | None = None) -> None:
        super().__init__(skills_root=skills_root)
        self.scout = JobScout()
        self.ats = ATSJobScout()

    def build_record(self, **kwargs: object) -> JobRecord:
        return self.execute(lambda: self.scout.build_record(**kwargs))

    def deduplicate(self, jobs: Iterable[JobRecord]) -> list[JobRecord]:
        return self.execute(lambda: self.scout.deduplicate(jobs))

    def ingest(self, jobs: Iterable[RawATSJob]) -> list[JobRecord]:
        return self.execute(lambda: self.ats.ingest(jobs))
