from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EvidenceKind(StrEnum):
    VERIFIED = "verified"
    USER_PROVIDED = "user_provided"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class SupportStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    source_type: str
    label: str


@dataclass(frozen=True)
class EvidenceClaim:
    claim_id: str
    claim: str
    kind: EvidenceKind
    support: SupportStatus
    confidence: float
    source: EvidenceSource | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.claim.strip():
            raise ValueError("Evidence claim cannot be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Evidence confidence must be between 0 and 1")
        if self.kind is EvidenceKind.VERIFIED and self.source is None:
            raise ValueError("Verified evidence requires a source")
        if self.support is SupportStatus.UNSUPPORTED and self.confidence > 0.5:
            raise ValueError("Unsupported evidence cannot have confidence above 0.5")


@dataclass(frozen=True)
class EvidenceLedger:
    claims: tuple[EvidenceClaim, ...] = field(default_factory=tuple)

    def add(self, claim: EvidenceClaim) -> "EvidenceLedger":
        if any(existing.claim_id == claim.claim_id for existing in self.claims):
            raise ValueError(f"Duplicate evidence claim id: {claim.claim_id}")
        return EvidenceLedger(self.claims + (claim,))

    def supported(self) -> tuple[EvidenceClaim, ...]:
        return tuple(c for c in self.claims if c.support is SupportStatus.SUPPORTED)

    def unsupported(self) -> tuple[EvidenceClaim, ...]:
        return tuple(c for c in self.claims if c.support is SupportStatus.UNSUPPORTED)

    def to_dict(self) -> dict[str, object]:
        return {
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "claim": c.claim,
                    "kind": c.kind.value,
                    "support": c.support.value,
                    "confidence": c.confidence,
                    "source": None if c.source is None else {
                        "source_id": c.source.source_id,
                        "source_type": c.source.source_type,
                        "label": c.source.label,
                    },
                    "notes": c.notes,
                }
                for c in self.claims
            ]
        }
