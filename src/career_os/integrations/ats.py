from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
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
    """Credential-free public ATS reader. Adapters normalize provider payloads only."""

    def fetch_json(self, url: str, *, timeout: float = 15.0) -> dict | list:
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "Career-OS-V2/0.1"})
        with urlopen(req, timeout=timeout) as response:
            if not 200 <= getattr(response, "status", 200) < 300:
                raise RuntimeError(f"ATS returned HTTP {response.status}")
            return json.loads(response.read().decode("utf-8"))


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
        return [
            RawATSJob(self.provider, str(item.get("id", "")), slug, item.get("text", ""),
                      (item.get("categories") or {}).get("location"),
                      item.get("descriptionPlain") or item.get("description"),
                      item.get("hostedUrl") or item.get("applyUrl", ""),
                      _iso_from_epoch_ms(item.get("createdAt")), item)
            for item in payload
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
    return None
