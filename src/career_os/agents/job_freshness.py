from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum

from career_os.models.job import JobEvidence, JobRecord, JobStatus


class Freshness(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class FreshnessEvaluator:
    """Evaluate posting age without inventing a posting date."""

    def evaluate(self, job: JobRecord, *, now: datetime | None = None, max_age_days: int = 45) -> Freshness:
        now = now or datetime.now(timezone.utc)
        if job.posted_at is None:
            job.risk_signals.append("POSTED_DATE_UNKNOWN")
            return Freshness.UNKNOWN
        posted = job.posted_at
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        age = now - posted
        checked_at = now
        if age < timedelta(0):
            job.risk_signals.append("POSTED_DATE_IN_FUTURE")
            result = Freshness.UNKNOWN
        elif age > timedelta(days=max_age_days):
            job.risk_signals.append(f"POSTING_OLDER_THAN_{max_age_days}_DAYS")
            result = Freshness.STALE
            if job.status is JobStatus.VERIFIED:
                job.status = JobStatus.UNKNOWN
        else:
            result = Freshness.FRESH
        job.verification_evidence.append(
            JobEvidence(
                source_url=job.source_url,
                checked_at=checked_at,
                signal=f"posting_freshness_{result.value.lower()}",
                detail=f"max_age_days={max_age_days}; posted_at={posted.isoformat()}; age_days={age.total_seconds()/86400:.2f}",
            )
        )
        return result
