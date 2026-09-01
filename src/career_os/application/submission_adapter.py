from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
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
    """Bridge Career OS approval/state to a verified browser provider.

    When the JobPilot local runtime is configured, it owns the authenticated
    browser/session and application mechanics. Career OS remains the approval,
    evidence and persistence control plane.
    """

    def __init__(self, manager: ApplicationManager | None = None, runner: Callable[..., Any] | None = None):
        self.manager = manager or ApplicationManager()
        self.runner = runner or self._default_runner

    @staticmethod
    def _default_runner(job: dict[str, Any], profile: dict[str, Any], resume_path: str) -> Any:
        if all(os.getenv(name, "").strip() for name in ("JOBPILOT_API", "JOBPILOT_API_TOKEN", "JOBPILOT_TERMINAL_URL")):
            from career_os.application.jobpilot_executor import JobPilotExecutor
            return JobPilotExecutor().execute(job, profile, resume_path)
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

        return ExecutionOutcome(state=state, submitted=submitted, evidence=evidence, blockers=blockers)
