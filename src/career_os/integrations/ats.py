from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse


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

    def fetch_json(self, url: str, *, timeout: float = 15.0) -> dict:
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "Career-OS-V2/0.1"})
        with urlopen(req, timeout=timeout) as response:
            if not 200 <= getattr(response, "status", 200) < 300:
                raise RuntimeError(f"ATS returned HTTP {response.status}")
            return json.loads(response.read().decode("utf-8"))


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
            RawATSJob(
                provider=self.provider,
                external_id=str(item.get("id", "")),
                company=slug,
                title=item.get("title", ""),
                location=(item.get("location") or {}).get("name"),
                description=item.get("content"),
                job_url=item.get("absolute_url", ""),
                posted_at=item.get("updated_at"),
                raw=item,
            )
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
            RawATSJob(
                provider=self.provider,
                external_id=str(item.get("id", "")),
                company=slug,
                title=item.get("text", ""),
                location=(item.get("categories") or {}).get("location"),
                description=item.get("descriptionPlain") or item.get("description"),
                job_url=item.get("hostedUrl") or item.get("applyUrl", ""),
                posted_at=str(item.get("createdAt")) if item.get("createdAt") is not None else None,
                raw=item,
            )
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
            RawATSJob(
                provider=self.provider,
                external_id=str(item.get("jobUrl", "")),
                company=slug,
                title=item.get("title", ""),
                location=item.get("location"),
                description=item.get("descriptionPlain") or item.get("descriptionHtml"),
                job_url=item.get("jobUrl", ""),
                posted_at=item.get("publishedAt") or item.get("updatedAt"),
                raw=item,
            )
            for item in payload.get("jobs", [])
        ]


def detect_ats(url: str) -> tuple[str, str] | None:
    host = urlparse(url).netloc.casefold()
    path = [part for part in urlparse(url).path.split("/") if part]
    if "greenhouse.io" in host and path:
        return "greenhouse", path[0]
    if "lever.co" in host and path:
        return "lever", path[0]
    if "ashbyhq.com" in host and path:
        return "ashby", path[0]
    return None
