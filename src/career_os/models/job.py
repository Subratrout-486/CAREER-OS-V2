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


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        host = f"{host}:{port}"
    path = parts.path.rstrip("/") or "/"
    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(("utm_", "fbclid")))
    )
    return urlunsplit((scheme, host, path, query, ""))


def canonical_job_key(company: str, title: str, location: str | None, url: str) -> str:
    normalized = "|".join(
        value.strip().casefold() for value in (company, title, location or "", canonicalize_url(url))
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
    canonical_key: str
    status: JobStatus = JobStatus.UNKNOWN
    description: str | None = None
    posted_at: datetime | None = None
    verification_evidence: list[JobEvidence] = Field(default_factory=list)
    duplicate_of: UUID | None = None
