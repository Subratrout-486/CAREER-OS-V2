from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from career_os.models.application import ApplicationRecord, ApplicationStatus


@dataclass(frozen=True)
class FollowUpAction:
    application_id: UUID
    due_at: datetime
    reason: str
    action: str


class FollowUpManager:
    """Plan deterministic, non-duplicating follow-up actions for live applications."""

    DEFAULT_DAYS = 7

    def schedule_after_submission(
        self,
        application: ApplicationRecord,
        *,
        submitted_at: datetime | None = None,
        days: int = DEFAULT_DAYS,
    ) -> ApplicationRecord:
        if application.status != ApplicationStatus.SUBMITTED:
            raise ValueError("Follow-up can only be scheduled after confirmed submission")
        if days < 1:
            raise ValueError("Follow-up interval must be at least one day")
        base = submitted_at or application.submission_confirmed_at
        if base is None:
            raise ValueError("A confirmed submission timestamp is required")
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        application.follow_up_at = base + timedelta(days=days)
        return application

    def due(self, application: ApplicationRecord, *, now: datetime | None = None) -> bool:
        if application.follow_up_at is None:
            return False
        if application.status not in {ApplicationStatus.SUBMITTED, ApplicationStatus.INTERVIEW}:
            return False
        current = now or datetime.now(timezone.utc)
        due_at = application.follow_up_at
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        return due_at <= current

    def plan(self, application: ApplicationRecord, *, now: datetime | None = None) -> FollowUpAction | None:
        if not self.due(application, now=now):
            return None
        reason = "No response recorded since application follow-up date"
        if application.status == ApplicationStatus.INTERVIEW:
            reason = "Interview-stage follow-up date reached"
        return FollowUpAction(
            application_id=application.application_id,
            due_at=application.follow_up_at,  # type: ignore[arg-type]
            reason=reason,
            action="Review current application state and send an appropriate follow-up; do not auto-send.",
        )

    def reschedule(self, application: ApplicationRecord, *, from_time: datetime, days: int = DEFAULT_DAYS) -> ApplicationRecord:
        if application.status not in {ApplicationStatus.SUBMITTED, ApplicationStatus.INTERVIEW}:
            raise ValueError("Only active applications can be rescheduled")
        if days < 1:
            raise ValueError("Follow-up interval must be at least one day")
        application.follow_up_at = from_time + timedelta(days=days)
        return application
