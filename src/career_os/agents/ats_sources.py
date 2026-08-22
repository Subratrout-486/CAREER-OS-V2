from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import json

from career_os.models.job import SourceType


@dataclass(frozen=True)
class RawATSJob:
    company: str
    title: str
    location: str | None
    description: str | None
    source_url: str
    apply_url: str | None
    posted_at: datetime | None
    source_type: SourceType
    ats: str
    external_id: str | None = None


def _dt(value: Any, *, milliseconds: bool = False) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if milliseconds:
            value /= 1000
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


class ATSClient:
    """Keyless public ATS readers. No browser, API key, or external connector required."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def _get_json(self, url: str) -> Any:
        request = Request(url, headers={"User-Agent": "Career-OS-V2/0.1 ATS client", "Accept": "application/json"})
        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read(4_000_000).decode("utf-8", errors="replace"))

    def greenhouse(self, board_token: str, company: str) -> list[RawATSJob]:
        data = self._get_json(f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true")
        jobs = [] if not isinstance(data, dict) else data.get("jobs", [])
        result = []
        for item in jobs:
            location = (item.get("location") or {}).get("name")
            result.append(RawATSJob(company, item.get("title", ""), location, item.get("content"), item.get("absolute_url", ""), item.get("absolute_url"), _dt(item.get("updated_at")), SourceType.ATS, "greenhouse", str(item.get("id")) if item.get("id") is not None else None))
        return result

    def lever(self, site: str, company: str) -> list[RawATSJob]:
        data = self._get_json(f"https://api.lever.co/v0/postings/{site}?mode=json")
        result = []
        for item in data if isinstance(data, list) else []:
            categories = item.get("categories") or {}
            result.append(RawATSJob(company, item.get("text", ""), categories.get("location"), item.get("description"), item.get("hostedUrl", ""), item.get("applyUrl"), _dt(item.get("createdAt"), milliseconds=True), SourceType.ATS, "lever", item.get("id")))
        return result

    def ashby(self, slug: str, company: str) -> list[RawATSJob]:
        data = self._get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        return [RawATSJob(company, item.get("title", ""), item.get("location"), item.get("descriptionHtml") or item.get("descriptionPlain"), item.get("jobUrl", ""), item.get("applyUrl"), _dt(item.get("publishedAt")), SourceType.ATS, "ashby", item.get("id")) for item in jobs]

    @staticmethod
    def detect(url: str) -> tuple[str, str] | None:
        host = urlparse(url).netloc.lower()
        path = urlparse(url).path.strip("/").split("/")
        if host == "boards.greenhouse.io" and path:
            return "greenhouse", path[0]
        if host == "jobs.lever.co" and path:
            return "lever", path[0]
        if host in {"jobs.ashbyhq.com", "api.ashbyhq.com"} and path:
            return "ashby", path[0]
        return None
