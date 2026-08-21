from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class JobStatus(StrEnum):
    VERIFIED = "VERIFIED"
    GHOST = "GHOST"
    DUPLICATE = "DUPLICATE"
    UNKNOWN = "UNKNOWN"


class SourceType(StrEnum):
    OFFICIAL_CAREER_PAGE = "OFFICIAL_CAREER_PAGE"
    ATS = "ATS"
    JOB_BOARD = "JOB_BOARD"
    SEARCH_RESULT = "SEARCH_RESULT"
    USER_SUBMITTED = "USER_SUBMITTED"
    UNKNOWN = "UNKNOWN"


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        host = f"{host}:{port}"
    path = parts.path.rstrip("/") or "/"
    ignored = {"fbclid", "gclid", "ref", "source", "src"}
    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_") and k.lower() not in ignored)
    )
    return urlunsplit((scheme, host, path, query, ""))


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def canonical_job_key(company: str, title: str, location: str | None, url: str) -> str:
    # URL identity is strongest when available; normalized metadata makes the key
    # stable across tracking URLs and minor source formatting differences.
    normalized = "|".join(
        (_normalize_text(company), _normalize_text(title), _normalize_text(location), canonicalize_url(url))
    )
    return sha256(normalized.encode("utf-8")).hexdigest()


def content_fingerprint(company: str, title: str, location: str | None, description: str | None) -> str:
    normalized = "|".join(
        (_normalize_text(company), _normalize_text(title), _normalize_text(location), _normalize_text(description))
    )
    return sha256(normalized.encode("utf-8")).hexdigest()


class JobEvidence(BaseModel):
    source_url: HttpUrl
    checked_at: datetime
    signal: str
    detail: str


class JobRecord(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    company: str
    title: str
    location: str | None = None
    source_url: HttpUrl
    source: str
    source_type: SourceType = SourceType.UNKNOWN
    canonical_key: str
    content_fingerprint: str | None = None
    status: JobStatus = JobStatus.UNKNOWN
    description: str | None = None
    posted_at: datetime | None = None
    verification_evidence: list[JobEvidence] = Field(default_factory=list)
    duplicate_of: UUID | None = None
    risk_signals: list[str] = Field(default_factory=list)
