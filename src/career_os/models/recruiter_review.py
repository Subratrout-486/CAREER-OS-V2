from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RecruiterReview:
    recommendation: str
    strengths: tuple[str, ...] = field(default_factory=tuple)
    objections: tuple[str, ...] = field(default_factory=tuple)
    risks: tuple[str, ...] = field(default_factory=tuple)
    fixes: tuple[str, ...] = field(default_factory=tuple)
    evidence_claim_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        allowed = {"shortlist", "manual_review", "do_not_shortlist"}
        if self.recommendation not in allowed:
            raise ValueError(f"Unknown recruiter recommendation: {self.recommendation}")

    def to_dict(self) -> dict[str, object]:
        return {
            "recommendation": self.recommendation,
            "strengths": list(self.strengths),
            "objections": list(self.objections),
            "risks": list(self.risks),
            "fixes": list(self.fixes),
            "evidence_claim_ids": list(self.evidence_claim_ids),
        }
