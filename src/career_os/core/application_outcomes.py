from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from career_os.models.application import ApplicationRecord, ApplicationStatus


@dataclass(frozen=True)
class OutcomeSummary:
    total: int
    submitted: int
    interviews: int
    offers: int
    rejected: int
    withdrawn: int
    closed: int
    submission_rate: float
    interview_rate: float
    offer_rate: float


class ApplicationOutcomeAnalyzer:
    """Turn recorded application states into auditable outcome metrics."""

    def summarize(self, applications: Iterable[ApplicationRecord]) -> OutcomeSummary:
        records = list(applications)
        total = len(records)
        submitted = sum(a.status in {ApplicationStatus.SUBMITTED, ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER, ApplicationStatus.REJECTED} for a in records)
        interviews = sum(a.status in {ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER} for a in records)
        offers = sum(a.status == ApplicationStatus.OFFER for a in records)
        rejected = sum(a.status == ApplicationStatus.REJECTED for a in records)
        withdrawn = sum(a.status == ApplicationStatus.WITHDRAWN for a in records)
        closed = sum(a.status == ApplicationStatus.CLOSED for a in records)
        return OutcomeSummary(
            total=total,
            submitted=submitted,
            interviews=interviews,
            offers=offers,
            rejected=rejected,
            withdrawn=withdrawn,
            closed=closed,
            submission_rate=round(submitted / total, 4) if total else 0.0,
            interview_rate=round(interviews / submitted, 4) if submitted else 0.0,
            offer_rate=round(offers / submitted, 4) if submitted else 0.0,
        )

    def rejection_counts(self, applications: Iterable[ApplicationRecord]) -> Counter[str]:
        """Count explicit rejection notes without inferring reasons not recorded."""
        counts: Counter[str] = Counter()
        for application in applications:
            if application.status != ApplicationStatus.REJECTED:
                continue
            for event in application.events:
                if event.to_status == ApplicationStatus.REJECTED and event.note:
                    counts[event.note] += 1
        return counts
