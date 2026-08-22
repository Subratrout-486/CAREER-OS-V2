from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SourceOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    FAILED = "FAILED"


class SourceRunDiagnostic(BaseModel):
    run_id: UUID = Field(default_factory=uuid4)
    source: str
    company: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    outcome: SourceOutcome = SourceOutcome.FAILED
    raw_found: int = 0
    normalized_found: int = 0
    duplicates: int = 0
    error: str | None = None
    retry_count: int = 0

    def finish(self, *, outcome: SourceOutcome, raw_found: int, normalized_found: int, duplicates: int = 0, error: str | None = None) -> None:
        self.outcome = outcome
        self.raw_found = raw_found
        self.normalized_found = normalized_found
        self.duplicates = duplicates
        self.error = error
        self.finished_at = datetime.now(timezone.utc)
