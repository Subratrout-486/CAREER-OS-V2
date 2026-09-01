from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from career_os.agents.application_manager import ApplicationManager
from career_os.models.application import ApplicationRecord


@dataclass(frozen=True)
class ExecutionOutcome:
    state: str
    submitted: bool
    evidence: tuple[str, ...]
    blockers: tuple[str, ...]


class ApplicationSubmissionAdapter:
    """Bridge Career OS approval/state to the existing controlled browser agent.

    The browser implementation remains in ``scripts/application_agent.py`` so
    there is one execution engine. This adapter owns the Career OS state
    transition and refuses to turn an unverified browser result into SUBMITTED.
    """

    def __init__(self, manager: ApplicationManager | None = None, runner: Callable[..., Any] | None = None):
        self.manager = manager or ApplicationManager()
        self.runner = runner or self._default_runner

    @staticmethod
    def _default_runner(job: dict[str, Any], profile: dict[str, Any], resume_path: str) -> Any:
        from scripts.application_agent import run_application

        return run_application(job, profile, resume_path)

    def execute(
        self,
        application: ApplicationRecord,
        *,
        job: dict[str, Any],
        profile: dict[str, Any],
        resume_path: str,
        submitted_at: datetime | None = None,
    ) -> ExecutionOutcome:
        if not self.manager.is_submission_ready(application):
            raise ValueError("Application must be explicitly approved and clean before browser execution")

        result = self.runner(job, profile, resume_path)
        evidence = tuple(str(item).strip() for item in getattr(result, "evidence", ()) if str(item).strip())
        blockers = tuple(str(item).strip() for item in getattr(result, "blockers", ()) if str(item).strip())
        submitted = bool(getattr(result, "submitted", False))
        state = str(getattr(result, "state", "unknown"))

        if submitted:
            if not evidence:
                raise ValueError("Browser reported submission without confirmation evidence")
            self.manager.confirm_submission(
                application,
                confirmation_evidence="; ".join(evidence),
                submitted_at=submitted_at,
            )

        return ExecutionOutcome(
            state=state,
            submitted=submitted,
            evidence=evidence,
            blockers=blockers,
        )
