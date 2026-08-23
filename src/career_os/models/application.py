from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class ApplicationStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    SUBMITTED = "SUBMITTED"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    CLOSED = "CLOSED"


class ApplicationEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    from_status: ApplicationStatus
    to_status: ApplicationStatus
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    note: str | None = None
    evidence: str | None = None


class ApplicationRecord(BaseModel):
    application_id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    source_url: HttpUrl
    company: str
    role: str
    resume_version: str | None = None
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    readiness_findings: list[str] = Field(default_factory=list)
    follow_up_at: datetime | None = None
    deadline_at: datetime | None = None
    submission_confirmed_at: datetime | None = None
    events: list[ApplicationEvent] = Field(default_factory=list)

    def transition(
        self,
        to_status: ApplicationStatus,
        *,
        note: str | None = None,
        evidence: str | None = None,
        now: datetime | None = None,
    ) -> ApplicationEvent:
        if to_status == self.status:
            raise ValueError(f"Application is already {self.status}")
        if to_status == ApplicationStatus.SUBMITTED and (not evidence or not evidence.strip()):
            raise ValueError("A confirmed submission requires evidence")
        if self.status in {ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED}:
            raise ValueError(f"Cannot transition a terminal application from {self.status}")

        allowed = {
            ApplicationStatus.DISCOVERED: {ApplicationStatus.READY_FOR_REVIEW, ApplicationStatus.WITHDRAWN},
            ApplicationStatus.READY_FOR_REVIEW: {ApplicationStatus.APPROVED, ApplicationStatus.DISCOVERED, ApplicationStatus.WITHDRAWN},
            ApplicationStatus.APPROVED: {ApplicationStatus.SUBMITTED, ApplicationStatus.WITHDRAWN},
            ApplicationStatus.SUBMITTED: {ApplicationStatus.INTERVIEW, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN},
            ApplicationStatus.INTERVIEW: {ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN},
            ApplicationStatus.OFFER: {ApplicationStatus.CLOSED, ApplicationStatus.WITHDRAWN},
        }
        if to_status not in allowed.get(self.status, set()):
            raise ValueError(f"Invalid application transition: {self.status} -> {to_status}")

        event = ApplicationEvent(
            from_status=self.status,
            to_status=to_status,
            occurred_at=now or datetime.now(timezone.utc),
            note=note,
            evidence=evidence,
        )
        self.events.append(event)
        self.status = to_status
        if to_status == ApplicationStatus.SUBMITTED:
            self.submission_confirmed_at = event.occurred_at
        return event
