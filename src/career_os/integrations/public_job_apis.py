from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from career_os.integrations.public_api_client import PublicAPIClient, PublicAPIError


def _dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _bool(value: object) -> bool | None:
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


def _float(value: object) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class PublicJob:
    provider: str
    external_id: str
    company: str
    title: str
    location: str | None
    description: str | None
    job_url: str
    posted_at: datetime | None
    remote: bool | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_is_predicted: bool | None = None
    employment_type: str | None = None
    tags: tuple[str, ...] = ()
    raw: dict[str, Any] | None = None

    def as_mapping(self) -> dict[str, object]:
        return self.__dict__.copy()


class AdzunaAdapter:
    provider = "adzuna"
    base_url = "https://api.adzuna.com/v1/api"
    currencies = {"in": "INR", "gb": "GBP", "us": "USD", "ca": "CAD", "au": "AUD", "de": "EUR", "fr": "EUR"}

    def __init__(self, app_id: str, app_key: str, *, client: PublicAPIClient | None = None) -> None:
        if not app_id or not app_key:
            raise ValueError("Adzuna app_id and app_key are required")
        self.app_id, self.app_key = app_id, app_key
        self.client = client or PublicAPIClient()

    def fetch(self, *, country: str = "in", query: str, location: str | None = None,
              pages: int = 1, results_per_page: int = 20) -> list[PublicJob]:
        if not query.strip() or not 1 <= pages <= 10 or not 1 <= results_per_page <= 50:
            raise ValueError("invalid Adzuna search settings")
        jobs: list[PublicJob] = []
        for page in range(1, pages + 1):
            params: dict[str, object] = {
                "app_id": self.app_id, "app_key": self.app_key, "what": query.strip(),
                "results_per_page": results_per_page, "content-type": "application/json",
            }
            if location:
                params["where"] = location.strip()
            url = f"{self.base_url}/jobs/{country.casefold()}/search/{page}?{urlencode(params)}"
            payload = self.client.get_json(url)
            if not isinstance(payload, dict) or not isinstance(payload.get("results", []), list):
                raise PublicAPIError("invalid Adzuna response shape")
            items = payload["results"]
            for item in items:
                if not isinstance(item, dict):
                    continue
                company = item.get("company") or {}
                loc = item.get("location") or {}
                title = str(item.get("title") or "").strip()
                name = str(company.get("display_name") or "").strip()
                job_url = str(item.get("redirect_url") or "").strip()
                if not title or not name or not job_url:
                    continue
                contract = " / ".join(str(x) for x in (item.get("contract_time"), item.get("contract_type")) if x)
                category = item.get("category") or {}
                jobs.append(PublicJob(
                    provider=self.provider,
                    external_id=str(item.get("id") or job_url),
                    company=name,
                    title=title,
                    location=str(loc.get("display_name") or "").strip() or None,
                    description=str(item.get("description") or "").strip() or None,
                    job_url=job_url,
                    posted_at=_dt(item.get("created")),
                    salary_min=_float(item.get("salary_min")),
                    salary_max=_float(item.get("salary_max")),
                    salary_currency=self.currencies.get(country.casefold()),
                    salary_is_predicted=_bool(item.get("salary_is_predicted")),
                    employment_type=contract or None,
                    tags=(str(category.get("label")),) if isinstance(category, dict) and category.get("label") else (),
                    raw=item,
                ))
            if len(items) < results_per_page:
                break
        return jobs


class ArbeitnowAdapter:
    provider = "arbeitnow"
    base_url = "https://www.arbeitnow.com/api/job-board-api"

    def __init__(self, *, client: PublicAPIClient | None = None, base_url: str | None = None) -> None:
        self.client = client or PublicAPIClient()
        self.base_url = (base_url or self.base_url).rstrip("/")
        if not self.base_url.startswith("https://"):
            raise ValueError("Arbeitnow base_url must use HTTPS")

    def fetch(self, *, query: str | None = None, location: str | None = None,
              remote_only: bool = False, visa_sponsorship: bool | None = None,
              pages: int = 1) -> list[PublicJob]:
        if not 1 <= pages <= 10:
            raise ValueError("Arbeitnow pages must be between 1 and 10")
        jobs: list[PublicJob] = []
        for page in range(1, pages + 1):
            params: dict[str, object] = {"page": page}
            if visa_sponsorship is not None:
                params["visa_sponsorship"] = "true" if visa_sponsorship else "false"
            payload = self.client.get_json(f"{self.base_url}?{urlencode(params)}")
            if not isinstance(payload, dict) or not isinstance(payload.get("data", []), list):
                raise PublicAPIError("invalid Arbeitnow response shape")
            items = payload["data"]
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                company = str(item.get("company_name") or "").strip()
                description = str(item.get("description") or "").strip() or None
                job_location = str(item.get("location") or "").strip() or None
                tags = tuple(str(x).strip() for x in item.get("tags", []) if str(x).strip())
                haystack = " ".join((title, company, description or "", *tags)).casefold()
                if query and query.casefold().strip() not in haystack:
                    continue
                if location and location.casefold().strip() not in (job_location or "").casefold():
                    continue
                remote = _bool(item.get("remote"))
                if remote_only and remote is not True:
                    continue
                job_url = str(item.get("url") or "").strip()
                if not title or not company or not job_url:
                    continue
                jobs.append(PublicJob(
                    provider=self.provider,
                    external_id=str(item.get("slug") or job_url),
                    company=company,
                    title=title,
                    location=job_location,
                    description=description,
                    job_url=job_url,
                    posted_at=_dt(item.get("created_at")),
                    remote=remote,
                    employment_type=", ".join(str(x) for x in item.get("job_types", []) if str(x).strip()) or None,
                    tags=tags,
                    raw=item,
                ))
            if not (payload.get("links") or {}).get("next"):
                break
        return jobs


@dataclass(frozen=True)
class OpenSkillsEnrichment:
    input_title: str
    canonical_title: str | None
    job_uuid: str | None
    skills: tuple[str, ...]


class OpenSkillsAdapter:
    """Optional title/skill enrichment; insecure HTTP is opt-in only."""

    provider = "open_skills"
    default_base_url = "http://api.dataatwork.org/v1"

    def __init__(self, *, client: PublicAPIClient | None = None,
                 base_url: str = default_base_url, allow_insecure_http: bool = False) -> None:
        self.client = client or PublicAPIClient()
        self.base_url = base_url.rstrip("/")
        if not self.base_url.startswith("https://") and not allow_insecure_http:
            raise ValueError("Open Skills requires HTTPS unless allow_insecure_http=True")

    def enrich_title(self, title: str, *, max_skills: int = 20) -> OpenSkillsEnrichment:
        if not title.strip() or max_skills < 1:
            raise ValueError("title and positive max_skills are required")
        normalized = self.client.get_json(f"{self.base_url}/jobs/normalize?{urlencode({'job_title': title.strip()})}")
        candidates = normalized if isinstance(normalized, list) else []
        canonical, job_uuid = None, None
        if candidates and isinstance(candidates[0], dict):
            first = candidates[0]
            canonical = str(first.get("description") or first.get("title") or "").strip() or None
            job_uuid = str(first.get("parent_uuid") or first.get("uuid") or "").strip() or None
        if not job_uuid:
            return OpenSkillsEnrichment(title, canonical, None, ())
        related = self.client.get_json(f"{self.base_url}/jobs/{job_uuid}/related_skills")
        skills: list[str] = []
        for item in related if isinstance(related, list) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("skill_name") or item.get("name") or "").strip()
            if name and name.casefold() not in {x.casefold() for x in skills}:
                skills.append(name)
            if len(skills) >= max_skills:
                break
        return OpenSkillsEnrichment(title, canonical, job_uuid, tuple(skills))
