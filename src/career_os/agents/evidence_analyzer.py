from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceLedger, SupportStatus


_QUANTIFIED = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%|percent|hours?|days?|months?|years?|tickets?|users?|customers?|projects?)\b", re.I)
_CERTIFICATION = re.compile(r"\b(certif(?:ied|ication)|certification|license|licence)\b", re.I)
_DATE_RANGE = re.compile(r"\b(?:19|20)\d{2}\s*(?:-|–|—|to)\s*(?:(?:19|20)\d{2}|present|current)\b", re.I)


class ConflictType(StrEnum):
    TEMPORAL = "temporal"
    QUANTITATIVE = "quantitative"
    CREDENTIAL = "credential"
    IDENTITY = "identity"


@dataclass(frozen=True)
class EvidenceConflict:
    first_claim_id: str
    second_claim_id: str
    conflict_type: ConflictType
    reason: str


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

    def conflicts(self, ledger: EvidenceLedger) -> tuple[EvidenceConflict, ...]:
        """Find deterministic conflicts without deciding which claim is true."""
        conflicts: list[EvidenceConflict] = []
        claims = ledger.claims
        for index, first in enumerate(claims):
            for second in claims[index + 1:]:
                conflict = self._pair_conflict(first, second)
                if conflict is not None:
                    conflicts.append(conflict)
        return tuple(conflicts)

    def has_conflicts(self, ledger: EvidenceLedger) -> bool:
        return bool(self.conflicts(ledger))

    def _pair_conflict(self, first: EvidenceClaim, second: EvidenceClaim) -> EvidenceConflict | None:
        left = first.claim.casefold().strip()
        right = second.claim.casefold().strip()
        if left == right:
            return None

        # Explicit numeric disagreement about the same normalized claim subject.
        left_numbers = _QUANTIFIED.findall(first.claim)
        right_numbers = _QUANTIFIED.findall(second.claim)
        if left_numbers and right_numbers:
            left_subject = _QUANTIFIED.sub("", left)
            right_subject = _QUANTIFIED.sub("", right)
            if self._similar_subject(left_subject, right_subject) and left_numbers != right_numbers:
                return EvidenceConflict(first.claim_id, second.claim_id, ConflictType.QUANTITATIVE, "Same claim subject has different quantified outcomes")

        # Certification/licence claims with different named credentials are treated as identity conflicts
        # only when both claims refer to the same credential family.
        if _CERTIFICATION.search(left) and _CERTIFICATION.search(right):
            left_cred = self._credential_subject(left)
            right_cred = self._credential_subject(right)
            if left_cred and right_cred and left_cred == right_cred and left != right:
                return EvidenceConflict(first.claim_id, second.claim_id, ConflictType.CREDENTIAL, "Credential claims disagree")

        # Temporal conflict is deliberately conservative: only claims sharing a clear employer/education
        # subject and explicit date ranges are considered. Free-form dates are not guessed.
        if _DATE_RANGE.search(left) and _DATE_RANGE.search(right):
            left_subject = _DATE_RANGE.sub("", left)
            right_subject = _DATE_RANGE.sub("", right)
            if self._similar_subject(left_subject, right_subject) and _DATE_RANGE.search(left).group(0) != _DATE_RANGE.search(right).group(0):
                return EvidenceConflict(first.claim_id, second.claim_id, ConflictType.TEMPORAL, "Same subject has incompatible date ranges")
        return None

    @staticmethod
    def _similar_subject(left: str, right: str) -> bool:
        normalize = lambda value: set(re.findall(r"[a-z0-9]+", value))
        left_tokens = normalize(left)
        right_tokens = normalize(right)
        if not left_tokens or not right_tokens:
            return False
        overlap = len(left_tokens & right_tokens)
        return overlap >= 2 or left_tokens == right_tokens

    @staticmethod
    def _credential_subject(value: str) -> str:
        value = _CERTIFICATION.sub("", value)
        tokens = re.findall(r"[a-z0-9]+", value)
        return " ".join(tokens[:4])

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
