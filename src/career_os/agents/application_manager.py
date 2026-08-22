from __future__ import annotations

from datetime import datetime
from uuid import UUID

from career_os.models.application import ApplicationRecord, ApplicationStatus
from career_os.models.job import JobRecord


class ApplicationManager:
    """Prepare and track applications without performing external submission."""

    def create(self, job: JobRecord, *, resume_version: str | None = None) -> ApplicationRecord:
        return ApplicationRecord(
            job_id=job.job_id,
            source_url=job.source_url,
            company=job.company,
            role=job.title,
            resume_version=resume_version,
        )

    def mark_ready(self, application: ApplicationRecord, findings: list[str] | None = None) -> ApplicationRecord:
        application.readiness_findings = list(findings or [])
        if application.readiness_findings:
            return application
        application.transition(ApplicationStatus.READY_FOR_REVIEW, note="Application package is ready for review")
        return application

    def approve(self, application: ApplicationRecord, *, note: str | None = None) -> ApplicationRecord:
        application.transition(ApplicationStatus.APPROVED, note=note or "Explicit approval recorded")
        return application

    def confirm_submission(
        self,
        application: ApplicationRecord,
        *,
        confirmation_evidence: str,
        submitted_at: datetime | None = None,
    ) -> ApplicationRecord:
        application.transition(
            ApplicationStatus.SUBMITTED,
            evidence=confirmation_evidence,
            now=submitted_at,
        )
        return application

    def schedule_follow_up(self, application: ApplicationRecord, when: datetime) -> ApplicationRecord:
        application.follow_up_at = when
        return application

    @staticmethod
    def is_submission_ready(application: ApplicationRecord) -> bool:
        return application.status == ApplicationStatus.APPROVED and not application.readiness_findings
