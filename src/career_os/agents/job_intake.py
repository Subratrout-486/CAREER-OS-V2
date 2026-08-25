from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone

from career_os.agents.job_scout import JobScout
from career_os.models.job import JobRecord, JobStatus, content_fingerprint


def _number(value: object) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _boolean(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    value = str(value).strip().casefold()
    if value in {"true", "1", "yes", "y"}:
        return True
    if value in {"false", "0", "no", "n"}:
        return False
    return None


class JobIntakePipeline:
    """Normalize structured job records into the canonical Job Scout pipeline."""

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
        location = ", ".join(str(x) for x in location_value if x) if isinstance(location_value, list) else str(location_value).strip() if location_value else None
        url = str(self._first(raw, "url", "source_url", "job_url", "absolute_url") or "").strip()
        source = str(self._first(raw, "source", "ats", "provider") or "unknown").strip()
        description_value = self._first(raw, "description", "content", "body")
        description = str(description_value) if description_value is not None else None

        job = self.scout.build_record(company=company, title=title, location=location,
                                      source_url=url, source=source, description=description)
        job.content_fingerprint = content_fingerprint(company, title, location, description)
        job.external_id = str(raw.get("external_id")) if raw.get("external_id") not in (None, "") else None
        job.remote = _boolean(raw.get("remote"))
        job.salary_min = _number(raw.get("salary_min"))
        job.salary_max = _number(raw.get("salary_max"))
        job.salary_currency = str(raw.get("salary_currency")) if raw.get("salary_currency") else None
        job.salary_is_predicted = _boolean(raw.get("salary_is_predicted"))
        job.employment_type = str(raw.get("employment_type")) if raw.get("employment_type") else None
        job.normalized_title = str(raw.get("normalized_title")) if raw.get("normalized_title") else None
        normalized_skills = raw.get("normalized_skills")
        if isinstance(normalized_skills, (list, tuple, set)):
            job.normalized_skills = [str(x).strip() for x in normalized_skills if str(x).strip()]
        tags = raw.get("tags")
        if isinstance(tags, (list, tuple, set)):
            job.tags = [str(tag).strip() for tag in tags if str(tag).strip()]
        risk_signals = raw.get("risk_signals")
        if isinstance(risk_signals, (list, tuple, set)):
            job.risk_signals.extend(str(x) for x in risk_signals if str(x))

        posted = self._first(raw, "posted_at", "published_at", "publication_date", "created_at")
        if isinstance(posted, datetime):
            job.posted_at = posted
        elif isinstance(posted, (int, float)):
            job.posted_at = datetime.fromtimestamp(float(posted), tz=timezone.utc)
        elif isinstance(posted, str) and posted.strip():
            try:
                job.posted_at = datetime.fromisoformat(posted.replace("Z", "+00:00"))
            except ValueError:
                job.risk_signals.append("UNPARSEABLE_POSTED_AT")
        return job

    def ingest(self, raw_jobs: Iterable[Mapping[str, object]]) -> list[JobRecord]:
        records = self.scout.deduplicate(self.normalize(raw) for raw in raw_jobs)
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
