"""Durable application execution state machine.

Rules of this boundary:

* Nothing executes on an external site until the application has been
  explicitly APPROVED by a human.
* Once APPROVED, ordinary form steps, navigation, uploads and standard
  application questions proceed without redundant confirmation.
* A SUCCEEDED submission is only ever recorded from genuine submission
  verification evidence - never guessed.
* Security challenges (CAPTCHA / bot detection) are detected and classified
  as BLOCKED_SECURITY_CHALLENGE. This module deliberately contains no
  technique to defeat, bypass, evade or circumvent those challenges.

State survives process restarts through atomic JSON persistence. Every
externally visible transition is written through a temporary file that is
renamed into place so a crash mid-write cannot corrupt state.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ExecutionStatus(str):
    """Lifecycle stages for one application from discovery to tracked outcome."""

    DISCOVERED = "DISCOVERED"
    INTAKE_COMPLETE = "INTAKE_COMPLETE"
    ANALYZED = "ANALYZED"
    SCORED = "SCORED"
    TAILORED = "TAILORED"
    ATS_AUDITED = "ATS_AUDITED"
    RECRUITER_REVIEWED = "RECRUITER_REVIEWED"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    APPROVED = "APPROVED"
    QUEUED = "QUEUED"
    APPLYING = "APPLYING"
    SUBMITTED = "SUBMITTED"
    SUBMISSION_VERIFIED = "SUBMISSION_VERIFIED"
    APPLICATION_FAILED = "APPLICATION_FAILED"
    BLOCKED_SECURITY_CHALLENGE = "BLOCKED_SECURITY_CHALLENGE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    WITHDRAWN = "WITHDRAWN"


_AUTO_PROGRESS = {
    ExecutionStatus.DISCOVERED: ExecutionStatus.INTAKE_COMPLETE,
    ExecutionStatus.INTAKE_COMPLETE: ExecutionStatus.ANALYZED,
    ExecutionStatus.ANALYZED: ExecutionStatus.SCORED,
    ExecutionStatus.SCORED: ExecutionStatus.TAILORED,
    ExecutionStatus.TAILORED: ExecutionStatus.ATS_AUDITED,
    ExecutionStatus.ATS_AUDITED: ExecutionStatus.RECRUITER_REVIEWED,
    ExecutionStatus.RECRUITER_REVIEWED: ExecutionStatus.READY_FOR_APPROVAL,
}

_EXECUTION_ORDER = [
    ExecutionStatus.APPROVED,
    ExecutionStatus.QUEUED,
    ExecutionStatus.APPLYING,
    ExecutionStatus.SUBMITTED,
    ExecutionStatus.SUBMISSION_VERIFIED,
]


@dataclass
class ExecutionEvent:
    status: str
    occurred_at: str = field(default_factory=lambda: _utcnow())
    detail: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApplicationExecution:
    """Durable state for one job's application pipeline."""

    execution_id: str = field(default_factory=lambda: str(uuid4()))
    job_key: str = ""
    company: str = ""
    title: str = ""
    application_url: str = ""
    status: str = ExecutionStatus.DISCOVERED
    pipeline: dict[str, Any] = field(default_factory=dict)
    approval: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    events: list[ExecutionEvent] = field(default_factory=list)
    retry_count: int = 0
    updated_at: str = field(default_factory=_utcnow)

    def record(self, status: str, *, detail: str = "", metadata: dict[str, Any] | None = None) -> None:
        self.status = status
        self.updated_at = _utcnow()
        self.events.append(
            ExecutionEvent(status=status, detail=detail, metadata=metadata or {})
        )


class ExecutionTransitionError(ValueError):
    pass


class ExecutionStore:
    """Atomic, restart-safe persistence for application executions."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, execution_id: str) -> Path:
        return self.root / f"{execution_id}.json"

    def save(self, execution: ApplicationExecution) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(execution), indent=2, sort_keys=True, default=str) + "\n"
        with tempfile.NamedTemporaryFile("w", dir=self.root, delete=False, encoding="utf-8") as handle:
            handle.write(payload)
            temp_name = handle.name
        Path(temp_name).replace(self._path(execution.execution_id))

    def load(self, execution_id: str) -> ApplicationExecution | None:
        path = self._path(execution_id)
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["events"] = [ExecutionEvent(**e) for e in raw.get("events", [])]
        return ApplicationExecution(**raw)

    def list(self) -> list[ApplicationExecution]:
        if not self.root.exists():
            return []
        executions = []
        for path in sorted(self.root.glob("*.json")):
            exc = self.load(path.stem)
            if exc is not None:
                executions.append(exc)
        return executions

    def by_status(self, status: str) -> list[ApplicationExecution]:
        return [e for e in self.list() if e.status == status]

    def by_job_key(self, job_key: str) -> list[ApplicationExecution]:
        return [e for e in self.list() if e.job_key == job_key]


class ApplicationExecutionStateMachine:
    """Enforces legal transitions and the approval gate for one execution."""

    def __init__(self, store: ExecutionStore, *, auto_approve: bool = False) -> None:
        self.store = store
        self.auto_approve = auto_approve

    def advance_to_ready(self, execution: ApplicationExecution) -> ApplicationExecution:
        """Walk the deterministic pipeline states up to READY_FOR_APPROVAL.

        This mutates in memory; the caller persists. No external action occurs.
        """
        for current, next_status in _AUTO_PROGRESS.items():
            if execution.status == current:
                execution.record(next_status)
        return execution

    def approve(self, execution: ApplicationExecution) -> ApplicationExecution:
        if execution.status != ExecutionStatus.READY_FOR_APPROVAL:
            raise ExecutionTransitionError(
                f"Cannot approve from {execution.status}; must be READY_FOR_APPROVAL"
            )
        execution.approval = {
            "approved": True,
            "approved_at": _utcnow(),
            "note": "Explicit human approval for autonomous execution",
        }
        execution.record(
            ExecutionStatus.APPROVED,
            detail="Approved by human; autonomous application execution authorized",
        )
        return execution

    def should_execute(self, execution: ApplicationExecution) -> bool:
        """An execution is allowed to touch an external site only when approved."""
        if self.auto_approve:
            return execution.status in {ExecutionStatus.APPROVED, ExecutionStatus.QUEUED}
        return (
            execution.status in {ExecutionStatus.APPROVED, ExecutionStatus.QUEUED}
            and bool(execution.approval.get("approved"))
        )

    def queue(self, execution: ApplicationExecution) -> ApplicationExecution:
        if not self.should_execute(execution):
            raise ExecutionTransitionError("Execution is not approved and cannot be queued")
        execution.record(
            ExecutionStatus.QUEUED,
            detail="Queued for autonomous browser execution",
        )
        return execution

    def begin_apply(self, execution: ApplicationExecution) -> ApplicationExecution:
        if execution.status != ExecutionStatus.QUEUED:
            raise ExecutionTransitionError("Cannot begin applying unless queued")
        execution.record(ExecutionStatus.APPLYING)
        return execution

    def mark_submitted(self, execution: ApplicationExecution, evidence: str) -> ApplicationExecution:
        if not evidence or not evidence.strip():
            raise ExecutionTransitionError("Submission requires verification evidence")
        execution.execution["submission_evidence"] = evidence
        execution.record(
            ExecutionStatus.SUBMITTED,
            detail="External submission observed with evidence",
        )
        return execution

    def verify_submission(self, execution: ApplicationExecution, evidence: str) -> ApplicationExecution:
        if execution.status != ExecutionStatus.SUBMITTED:
            raise ExecutionTransitionError("Cannot verify a submission that was not SUBMITTED")
        if not evidence or not evidence.strip():
            raise ExecutionTransitionError("Verification requires evidence")
        execution.execution["verification_evidence"] = evidence
        execution.record(
            ExecutionStatus.SUBMISSION_VERIFIED,
            detail="Submission independently verified",
        )
        return execution

    def fail(self, execution: ApplicationExecution, reason: str) -> ApplicationExecution:
        execution.execution["failure_reason"] = reason
        execution.record(ExecutionStatus.APPLICATION_FAILED, detail=reason)
        return execution

    def block_security_challenge(self, execution: ApplicationExecution, detail: str) -> ApplicationExecution:
        """Record a security challenge as a hard stop. No bypass logic exists here."""
        execution.execution["security_challenge"] = detail
        execution.record(
            ExecutionStatus.BLOCKED_SECURITY_CHALLENGE,
            detail="Security challenge detected; application paused for human review",
        )
        return execution

    def auth_required(self, execution: ApplicationExecution, detail: str) -> ApplicationExecution:
        """Record that the application flow requires human authentication.

        Distinct from NEEDS_REVIEW: this is a specific, actionable blocker where
        the candidate must sign in / authorize before auto-apply can continue.
        Never bypassed; surfaced to the user as AUTH_REQUIRED.
        """
        execution.execution["auth_required"] = detail
        execution.record(
            ExecutionStatus.AUTH_REQUIRED,
            detail=detail or "Authentication required to continue application",
        )
        return execution

    def unsupported(self, execution: ApplicationExecution, detail: str) -> ApplicationExecution:
        """Record that no supported auto-apply flow maps to this application.

        A genuine product state: the application portal / URL is recognized as
        one the adapter does not yet drive autonomously, so the job goes back to
        the human rather than being guessed at or force-submitted.
        """
        execution.execution["unsupported"] = detail
        execution.record(
            ExecutionStatus.UNSUPPORTED,
            detail=detail or "No supported auto-apply flow for this application",
        )
        return execution

    def needs_review(self, execution: ApplicationExecution, detail: str) -> ApplicationExecution:
        execution.record(ExecutionStatus.NEEDS_REVIEW, detail=detail)
        return execution

    def withdraw(self, execution: ApplicationExecution, detail: str = "") -> ApplicationExecution:
        execution.record(ExecutionStatus.WITHDRAWN, detail=detail or "Withdrawn by user")
        return execution
