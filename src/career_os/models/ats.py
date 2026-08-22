from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ATSSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class ATSFinding:
    code: str
    severity: ATSSeverity
    message: str


@dataclass(frozen=True)
class ATSAudit:
    score: float
    findings: tuple[ATSFinding, ...] = field(default_factory=tuple)
    matched_keywords: tuple[str, ...] = field(default_factory=tuple)
    missing_keywords: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "findings": [
                {"code": f.code, "severity": f.severity.value, "message": f.message}
                for f in self.findings
            ],
            "matched_keywords": list(self.matched_keywords),
            "missing_keywords": list(self.missing_keywords),
        }
