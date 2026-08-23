from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
from xml.etree import ElementTree

from career_os.integrations.ats import ATSClient, RawATSJob


@dataclass(frozen=True)
class SmartRecruitersAdapter:
    """Read SmartRecruiters' public company postings API without credentials."""

    client: ATSClient
    provider: str = "smartrecruiters"

    def __init__(self, client: ATSClient | None = None):
        object.__setattr__(self, "client", client or ATSClient())

    @staticmethod
    def api_url(company: str, *, limit: int = 100, offset: int = 0) -> str:
        if not company or limit <= 0 or limit > 100:
            raise ValueError("company is required and limit must be 1..100")
        return f"https://api.smartrecruiters.com/v1/companies/{company}/postings?limit={limit}&offset={offset}"

    def fetch(self, company: str, *, limit: int = 100, max_jobs: int = 500) -> list[RawATSJob]:
        jobs: list[RawATSJob] = []
        offset = 0
        while len(jobs) < max_jobs:
            payload = self.client.fetch_json(self.api_url(company, limit=limit, offset=offset))
            postings = payload.get("content", []) if isinstance(payload, dict) else []
            if not postings:
                break
            for item in postings:
                ref = item.get("ref", {}) or {}
                external_id = str(ref.get("id") or item.get("id") or "")
                jobs.append(RawATSJob(
                    self.provider,
                    external_id,
                    company,
                    item.get("name", ""),
                    ((item.get("location") or {}).get("city") or "") or None,
                    item.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text") if isinstance(item.get("jobAd"), dict) else None,
                    ref.get("jobAdUrl") or ref.get("url") or "",
                    item.get("releasedDate") or item.get("lastUpdateDate"),
                    item,
                ))
                if len(jobs) >= max_jobs:
                    break
            if len(postings) < limit:
                break
            offset += limit
        return jobs


@dataclass(frozen=True)
class TeamtailorRSSAdapter:
    """Read Teamtailor's public zero-auth jobs RSS feed."""

    client: ATSClient
    provider: str = "teamtailor"

    def __init__(self, client: ATSClient | None = None):
        object.__setattr__(self, "client", client or ATSClient())

    @staticmethod
    def feed_url(careers_url: str) -> str:
        parsed = urlparse(careers_url)
        if not parsed.hostname or "teamtailor.com" not in parsed.hostname.casefold():
            raise ValueError("Teamtailor careers_url must use a *.teamtailor.com host")
        return f"{parsed.scheme or 'https'}://{parsed.netloc}/jobs.rss"

    def fetch(self, careers_url: str) -> list[RawATSJob]:
        # ATSClient exposes JSON transport; RSS needs a text response, so use a
        # small adapter seam. Production callers can provide a client exposing
        # fetch_text; tests can inject a deterministic fixture client.
        fetch_text = getattr(self.client, "fetch_text", None)
        if fetch_text is None:
            raise RuntimeError("TeamtailorRSSAdapter requires an ATS client with fetch_text()")
        xml = fetch_text(self.feed_url(careers_url))
        root = ElementTree.fromstring(xml)
        company = urlparse(careers_url).hostname.split(".")[0]  # type: ignore[union-attr]
        jobs: list[RawATSJob] = []
        for item in root.findall(".//item"):
            def text(tag: str) -> str:
                return (item.findtext(tag) or "").strip()

            link = text("link")
            jobs.append(RawATSJob(
                self.provider,
                link or text("guid"),
                company,
                text("title"),
                text("tt:location") or None,
                text("description") or None,
                link,
                text("pubDate") or None,
                {child.tag: child.text for child in item},
            ))
        return jobs


def detect_public_provider(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if host.endswith(".teamtailor.com"):
        return "teamtailor", url
    if "smartrecruiters.com" in host:
        parts = [p for p in parsed.path.split("/") if p]
        if parts:
            return "smartrecruiters", parts[-1]
    return None
