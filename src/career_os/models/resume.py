from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResumeBullet:
    text: str
    evidence_claim_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResumeProfile:
    summary: str
    bullets: tuple[ResumeBullet, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TailoredResume:
    summary: str
    bullets: tuple[ResumeBullet, ...]
    matched_keywords: tuple[str, ...] = field(default_factory=tuple)
    omitted_claim_ids: tuple[str, ...] = field(default_factory=tuple)
    edit_trace: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "bullets": [
                {"text": bullet.text, "evidence_claim_ids": list(bullet.evidence_claim_ids)}
                for bullet in self.bullets
            ],
            "matched_keywords": list(self.matched_keywords),
            "omitted_claim_ids": list(self.omitted_claim_ids),
            "edit_trace": list(self.edit_trace),
        }
