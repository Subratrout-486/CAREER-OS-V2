from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class RawATSJob:
    provider: str
    external_id: str
    company: str
    title: str
    location: str | None
    description: str | None
    job_url: str
    posted_at: str | None
    raw: dict


class ATSClient:
    """Credential-free public ATS reader with bounded retries and backoff.

    Adapters normalize provider payloads only. Transport behavior is centralized
    so every ATS gets the same timeout, retry, throttling and HTTP error policy.
    """

    _RETRYABLE_HTTP_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})

    def __init__(self, *, retries: int = 2, backoff_seconds: float = 0.5):
        if retries < 0:
            raise ValueError("retries must be non-negative")
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative")
        self.retries = retries
        self.backoff_seconds = backoff_seconds

    def _request_json(self, request: Request, *, timeout: float) -> dict | list:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=timeout) as response:
                    status = getattr(response, "status", 200)
                    if not 200 <= status < 300:
                        raise RuntimeError(f"ATS returned HTTP {status}")
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                last_error = exc
                if exc.code not in self._RETRYABLE_HTTP_STATUS:
                    raise RuntimeError(f"ATS returned HTTP {exc.code}") from exc
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc

            if attempt < self.retries:
                time.sleep(self.backoff_seconds * (2**attempt))

        raise RuntimeError("ATS request failed after retries") from last_error

    def fetch_json(self, url: str, *, timeout: float = 15.0) -> dict | list:
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "Career-OS-V2/0.1"})
        return self._request_json(req, timeout=timeout)

    def post_json(self, url: str, payload: dict, *, timeout: float = 15.0) -> dict | list:
        body = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Career-OS-V2/0.1",
            },
        )
        return self._request_json(req, timeout=timeout)


def _iso_from_epoch_ms(value: object) -> str | None:
    if value in (None, ""):
        return None
    try:
        milliseconds = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


class GreenhouseAdapter:
    provider = "greenhouse"

    def __init__(self, client: ATSClient | None = None):
        self.client = client or ATSClient()

    @staticmethod
    def api_url(slug: str) -> str:
        return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"

    def fetch(self, slug: str) -> list[RawATSJob]:
        payload = self.client.fetch_json(self.api_url(slug))
        return [
            RawATSJob(self.provider, str(item.get("id", "")), slug, item.get("title", ""),
                      (item.get("location") or {}).get("name"), item.get("content"),
                      item.get("absolute_url", ""), item.get("first_published") or item.get("updated_at"), item)
            for item in payload.get("jobs", [])
        ]


class LeverAdapter:
    provider = "lever"

    def __init__(self, client: ATSClient | None = None):
        self.client = client or ATSClient()

    @staticmethod
    def api_url(slug: str) -> str:
        return f"https://api.lever.co/v0/postings/{slug}?mode=json"

    def fetch(self, slug: str) -> list[RawATSJob]:
        payload = self.client.fetch_json(self.api_url(slug))
        # Lever's public postings endpoint returns a JSON array. Accepting a
        # {"jobs": [...]} wrapper as well makes the adapter tolerant of cached
        # fixtures/proxies without changing the canonical adapter contract.
        items = payload.get("jobs", []) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise ValueError("Lever postings payload must contain a list of jobs")
        return [
            RawATSJob(self.provider, str(item.get("id", "")), slug, item.get("text", ""),
                      (item.get("categories") or {}).get("location"),
                      item.get("descriptionPlain") or item.get("description"),
                      item.get("hostedUrl") or item.get("applyUrl", ""),
                      _iso_from_epoch_ms(item.get("createdAt")), item)
            for item in items
        ]


class AshbyAdapter:
    provider = "ashby"

    def __init__(self, client: ATSClient | None = None):
        self.client = client or ATSClient()

    @staticmethod
    def api_url(slug: str) -> str:
        return f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"

    def fetch(self, slug: str) -> list[RawATSJob]:
        payload = self.client.fetch_json(self.api_url(slug))
        return [
            RawATSJob(self.provider, str(item.get("jobUrl", "")), slug, item.get("title", ""),
                      item.get("location"), item.get("descriptionPlain") or item.get("descriptionHtml"),
                      item.get("jobUrl", ""), item.get("publishedAt") or item.get("updatedAt"), item)
            for item in payload.get("jobs", [])
        ]


class WorkdayAdapter:
    """Read the public Workday CXS jobs endpoint for a known careers-board URL."""

    provider = "workday"

    def __init__(self, client: ATSClient | None = None):
        self.client = client or ATSClient()

    @staticmethod
    def api_url(board_url: str) -> str:
        parsed = urlparse(board_url)
        parts = [part for part in parsed.path.split("/") if part]
        if not parsed.hostname or ".myworkdayjobs.com" not in parsed.hostname or not parts:
            raise ValueError("Workday board_url must be a *.myworkdayjobs.com careers URL")
        tenant = parsed.hostname.split(".")[0]
        site_index = next((i for i, part in enumerate(parts) if part.casefold() not in {"en-us", "en-gb", "en-ca", "en-in"}), None)
        if site_index is None:
            raise ValueError("Workday board URL does not contain a site")
        site = parts[site_index]
        return f"{parsed.scheme}://{parsed.hostname}/wday/cxs/{tenant}/{site}/jobs"

    @staticmethod
    def _job_url(board_url: str, external_path: str) -> str:
        parsed = urlparse(board_url)
        base = f"{parsed.scheme}://{parsed.hostname}"
        return f"{base}{external_path}" if external_path.startswith("/") else f"{base}/{external_path}"

    def fetch(self, board_url: str, *, limit: int = 20, max_jobs: int = 100) -> list[RawATSJob]:
        if limit <= 0 or limit > 20:
            raise ValueError("Workday limit must be between 1 and 20")
        jobs: list[RawATSJob] = []
        offset = 0
        endpoint = self.api_url(board_url)
        company = urlparse(board_url).hostname.split(".")[0]  # type: ignore[union-attr]
        while len(jobs) < max_jobs:
            payload = self.client.post_json(endpoint, {"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": ""})
            postings = payload.get("jobPostings", [])
            if not postings:
                break
            for item in postings:
                external_path = item.get("externalPath", "")
                external_id = external_path.rsplit("_", 1)[-1] or external_path
                jobs.append(RawATSJob(
                    self.provider, str(external_id), company, item.get("title", ""),
                    item.get("locationsText"), item.get("jobDescription", "") or item.get("description", ""),
                    self._job_url(board_url, external_path), item.get("postedOn") or item.get("postedDate"), item,
                ))
                if len(jobs) >= max_jobs:
                    break
            if len(postings) < limit:
                break
            offset += limit
        return jobs


class RipplingAdapter:
    provider = "rippling"

    def __init__(self, client: ATSClient | None = None):
        self.client = client or ATSClient()

    @staticmethod
    def api_url(slug: str) -> str:
        return f"https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs"

    def fetch(self, slug: str) -> list[RawATSJob]:
        payload = self.client.fetch_json(self.api_url(slug))
        items = payload.get("jobs", payload) if isinstance(payload, dict) else payload
        return [
            RawATSJob(
                self.provider, str(item.get("id") or item.get("jobId") or item.get("slug") or ""), slug,
                item.get("title", ""), item.get("location") or item.get("locationName"),
                item.get("description") or item.get("descriptionHtml"),
                item.get("url") or item.get("jobUrl") or item.get("applyUrl", ""),
                item.get("publishedAt") or item.get("createdAt") or item.get("postedAt"), item,
            )
            for item in items
        ]


def detect_ats(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    host = parsed.netloc.casefold()
    path = [part for part in parsed.path.split("/") if part]
    if "greenhouse.io" in host and path:
        return "greenhouse", path[0]
    if "lever.co" in host and path:
        return "lever", path[0]
    if "ashbyhq.com" in host and path:
        return "ashby", path[0]
    if "myworkdayjobs.com" in host and path:
        return "workday", url
    if "rippling.com" in host and path:
        return "rippling", path[-1]
    return None
