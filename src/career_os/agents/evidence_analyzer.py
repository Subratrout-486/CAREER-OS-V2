from __future__ import annotations

import re

from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceLedger, SupportStatus


_QUANTIFIED = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%|percent|hours?|days?|months?|years?|tickets?|users?|customers?|projects?)\b", re.I)
_CERTIFICATION = re.compile(r"\b(certif(?:ied|ication)|certification|license|licence)\b", re.I)


class EvidenceAnalyzer:
    """Validate and organize explicitly supplied candidate evidence without inference."""

    def build_ledger(self, claims: list[EvidenceClaim]) -> EvidenceLedger:
        ledger = EvidenceLedger()
        for claim in claims:
            self._validate_material_claim(claim)
            ledger = ledger.add(claim)
        return ledger

    def material_gaps(self, ledger: EvidenceLedger) -> tuple[EvidenceClaim, ...]:
        return tuple(
            claim for claim in ledger.claims
            if claim.support in {SupportStatus.UNSUPPORTED, SupportStatus.CONTRADICTED}
            or claim.kind in {EvidenceKind.INFERRED, EvidenceKind.UNKNOWN}
        )

    def supported_claims(self, ledger: EvidenceLedger) -> tuple[EvidenceClaim, ...]:
        return tuple(
            claim for claim in ledger.claims
            if claim.support is SupportStatus.SUPPORTED
            and claim.kind in {EvidenceKind.VERIFIED, EvidenceKind.USER_PROVIDED}
        )

    def _validate_material_claim(self, claim: EvidenceClaim) -> None:
        if claim.kind is EvidenceKind.VERIFIED and claim.source is None:
            raise ValueError("Verified material evidence requires provenance")
        if claim.support in {SupportStatus.UNSUPPORTED, SupportStatus.CONTRADICTED} and claim.kind is EvidenceKind.VERIFIED:
            raise ValueError("Verified evidence cannot be marked unsupported or contradicted")
        if (_QUANTIFIED.search(claim.claim) or _CERTIFICATION.search(claim.claim)) and claim.kind in {
            EvidenceKind.INFERRED,
            EvidenceKind.UNKNOWN,
        }:
            raise ValueError("Quantified outcomes and certifications require explicit evidence")
