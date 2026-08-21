from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class AuditEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent: str
    details: dict[str, object] = Field(default_factory=dict)


class JobRecord(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    company: str
    title: str
    location: str | None = None
    source_url: HttpUrl
    source: str
    canonical_key: str
    status: Literal["VERIFIED", "GHOST", "DUPLICATE", "UNKNOWN"] = "UNKNOWN"
    verification_evidence: list[str] = Field(default_factory=list)
    audit: list[AuditEvent] = Field(default_factory=list)


class AgentResult(BaseModel):
    agent: str
    status: Literal["SUCCESS", "BLOCKED", "FAILED"]
    output: dict[str, object] = Field(default_factory=dict)
    audit: list[AuditEvent] = Field(default_factory=list)
