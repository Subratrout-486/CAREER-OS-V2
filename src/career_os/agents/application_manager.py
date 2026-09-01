from __future__ import annotations

from datetime import datetime

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
        evidence = confirmation_evidence.strip()
        if not evidence:
            raise ValueError("A confirmed submission requires evidence")

        # A browser retry can happen after the external site already confirmed
        # submission. Treat the same confirmation as idempotent and never append
        # a second SUBMITTED event. Conflicting evidence is rejected because it
        # may indicate a different application or stale execution result.
        if application.status == ApplicationStatus.SUBMITTED:
            previous = next(
                (event.evidence for event in reversed(application.events)
                 if event.to_status == ApplicationStatus.SUBMITTED),
                None,
            )
            if previous == evidence:
                return application
            raise ValueError("Application is already SUBMITTED with different evidence")

        application.transition(
            ApplicationStatus.SUBMITTED,
            evidence=evidence,
            now=submitted_at,
        )
        return application

    def schedule_follow_up(self, application: ApplicationRecord, when: datetime) -> ApplicationRecord:
        application.follow_up_at = when
        return application

    @staticmethod
    def is_submission_ready(application: ApplicationRecord) -> bool:
        return application.status == ApplicationStatus.APPROVED and not application.readiness_findings
