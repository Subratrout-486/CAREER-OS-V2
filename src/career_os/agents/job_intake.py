from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime

from career_os.agents.job_scout import JobScout
from career_os.models.job import JobRecord, JobStatus, SourceType, content_fingerprint


class JobIntakePipeline:
    """Normalize structured ATS records into the canonical Job Scout pipeline.

    The pipeline is deterministic and idempotent: normalization happens before
    duplicate detection, and every decision remains represented on the record.
    """

    def __init__(self, scout: JobScout | None = None) -> None:
        self.scout = scout or JobScout()

    @staticmethod
    def _first(data: Mapping[str, object], *keys: str) -> object | None:
        for key in keys:
            value = data.get(key)
            if value not in (None, ""):
                return value
        return None

    def normalize(self, raw: Mapping[str, object]) -> JobRecord:
        company = str(self._first(raw, "company", "company_name", "organization") or "").strip()
        title = str(self._first(raw, "title", "job_title", "name") or "").strip()
        location_value = self._first(raw, "location", "locations")
        if isinstance(location_value, list):
            location = ", ".join(str(x) for x in location_value if x)
        else:
            location = str(location_value).strip() if location_value else None
        url = str(self._first(raw, "url", "source_url", "job_url", "absolute_url") or "").strip()
        source = str(self._first(raw, "source", "ats", "provider") or "unknown").strip()
        description = self._first(raw, "description", "content", "body")
        description = str(description) if description is not None else None

        job = self.scout.build_record(
            company=company,
            title=title,
            location=location,
            source_url=url,
            source=source,
            description=description,
        )
        job.source_type = SourceType.ATS
        job.content_fingerprint = content_fingerprint(company, title, location, description)

        posted = self._first(raw, "posted_at", "published_at", "publication_date", "created_at")
        if isinstance(posted, datetime):
            job.posted_at = posted
        elif isinstance(posted, str) and posted.strip():
            try:
                job.posted_at = datetime.fromisoformat(posted.replace("Z", "+00:00"))
            except ValueError:
                job.risk_signals.append("UNPARSEABLE_POSTED_AT")

        return job

    def ingest(self, raw_jobs: Iterable[Mapping[str, object]]) -> list[JobRecord]:
        records = [self.normalize(raw) for raw in raw_jobs]
        records = self.scout.deduplicate(records)

        # JobScout already determines duplicate identity. This second pass adds
        # the explicit content signal so downstream verification/audit can tell
        # URL/key duplicates from the same listing appearing at different URLs.
        first_by_fingerprint: dict[str, JobRecord] = {}
        for job in records:
            if not job.content_fingerprint:
                continue
            existing = first_by_fingerprint.get(job.content_fingerprint)
            if existing is not None and existing.job_id != job.job_id:
                job.status = JobStatus.DUPLICATE
                job.duplicate_of = existing.job_id
                if "CONTENT_DUPLICATE" not in job.risk_signals:
                    job.risk_signals.append("CONTENT_DUPLICATE")
            else:
                first_by_fingerprint[job.content_fingerprint] = job
        return records
