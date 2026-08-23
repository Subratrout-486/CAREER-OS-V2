from __future__ import annotations

from dataclasses import dataclass

from career_os.models.application import ApplicationRecord
from career_os.models.fit import FitScore
from career_os.models.resume import TailoredResume


@dataclass(frozen=True)
class ApplicationPackage:
    """Auditable package prepared before any external application action."""

    application_id: str
    resume: TailoredResume
    fit: FitScore
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ready_for_review(self) -> bool:
        return not self.blockers


class ApplicationPackageBuilder:
    """Combine independent career-intelligence outputs into a review package."""

    def build(
        self,
        application: ApplicationRecord,
        fit: FitScore,
        resume: TailoredResume,
        *,
        required_resume_fields_present: bool = True,
        application_url_verified: bool = True,
    ) -> ApplicationPackage:
        blockers: list[str] = []
        warnings: list[str] = []

        if fit.hard_gaps:
            blockers.append("Missing hard requirements: " + "; ".join(fit.hard_gaps))
        if not required_resume_fields_present:
            blockers.append("Resume package is missing required fields")
        if not application_url_verified:
            blockers.append("Application URL has not been verified")
        if fit.preferred_gaps:
            warnings.append("Preferred gaps: " + "; ".join(fit.preferred_gaps))
        if not resume.matched_keywords:
            warnings.append("No JD keywords were found in the selected resume")

        return ApplicationPackage(
            application_id=str(application.application_id),
            resume=resume,
            fit=fit,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )
