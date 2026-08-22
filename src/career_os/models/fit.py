from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class RequirementStatus(StrEnum):
    MATCHED = "matched"
    PARTIALLY_MATCHED = "partially_matched"
    MISSING = "missing"


@dataclass(frozen=True)
class RequirementEvaluation:
    requirement: str
    status: RequirementStatus
    evidence_claim_ids: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0


@dataclass(frozen=True)
class FitScore:
    overall: float
    hard_requirements: float
    preferred_requirements: float
    skills: float
    hard_gaps: tuple[str, ...] = field(default_factory=tuple)
    preferred_gaps: tuple[str, ...] = field(default_factory=tuple)
    evidence_claim_ids: tuple[str, ...] = field(default_factory=tuple)
    recommendation: str = "weak_fit"

    def __post_init__(self) -> None:
        for value in (self.overall, self.hard_requirements, self.preferred_requirements, self.skills):
            if not 0.0 <= value <= 100.0:
                raise ValueError("Fit scores must be between 0 and 100")

    def to_dict(self) -> dict[str, object]:
        return {
            "overall": self.overall,
            "hard_requirements": self.hard_requirements,
            "preferred_requirements": self.preferred_requirements,
            "skills": self.skills,
            "hard_gaps": list(self.hard_gaps),
            "preferred_gaps": list(self.preferred_gaps),
            "evidence_claim_ids": list(self.evidence_claim_ids),
            "recommendation": self.recommendation,
        }
