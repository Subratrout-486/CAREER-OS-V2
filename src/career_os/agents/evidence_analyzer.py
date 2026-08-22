from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceLedger, SupportStatus


_QUANTIFIED = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:%|percent|hours?|days?|months?|years?|tickets?|users?|customers?|projects?)(?=\s|$|[.,;:])",
    re.I,
)
_CERTIFICATION = re.compile(r"\b(certif(?:ied|ication)|certification|license|licence)\b", re.I)
_DATE_RANGE = re.compile(r"\b(?:19|20)\d{2}\s*(?:-|–|—|to)\s*(?:(?:19|20)\d{2}|present|current)\b", re.I)
_EMPLOYMENT_SUBJECT = re.compile(r"\bworked\s+at\s+(.+?)\s+from\b", re.I)
_EDUCATION_SUBJECT = re.compile(r"\b(?:studied|attended|graduated)\s+(?:at|from)\s+(.+?)\s+from\b", re.I)


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

        # Numeric disagreement is only a conflict when the non-numeric claim subject matches.
        left_numbers = tuple(_QUANTIFIED.findall(first.claim))
        right_numbers = tuple(_QUANTIFIED.findall(second.claim))
        if left_numbers and right_numbers:
            left_subject = _QUANTIFIED.sub("", left)
            right_subject = _QUANTIFIED.sub("", right)
            if self._similar_subject(left_subject, right_subject) and left_numbers != right_numbers:
                return EvidenceConflict(
                    first.claim_id,
                    second.claim_id,
                    ConflictType.QUANTITATIVE,
                    "Same claim subject has different quantified outcomes",
                )

        # Certification/licence claims with different named credentials are treated as credential
        # conflicts only when they resolve to the same credential family.
        if _CERTIFICATION.search(left) and _CERTIFICATION.search(right):
            left_cred = self._credential_subject(left)
            right_cred = self._credential_subject(right)
            if left_cred and right_cred and left_cred == right_cred and left != right:
                return EvidenceConflict(
                    first.claim_id,
                    second.claim_id,
                    ConflictType.CREDENTIAL,
                    "Credential claims disagree",
                )

        # Temporal detection is deliberately conservative. We only compare claims when
        # an explicit employer/education subject can be extracted. This prevents common
        # words such as "worked", "at", and "from" from making unrelated employers conflict.
        if _DATE_RANGE.search(left) and _DATE_RANGE.search(right):
            left_subject = self._temporal_subject(left)
            right_subject = self._temporal_subject(right)
            left_range = _DATE_RANGE.search(left).group(0)
            right_range = _DATE_RANGE.search(right).group(0)
            if (
                left_subject
                and right_subject
                and self._same_subject(left_subject, right_subject)
                and left_range != right_range
            ):
                return EvidenceConflict(
                    first.claim_id,
                    second.claim_id,
                    ConflictType.TEMPORAL,
                    "Same subject has incompatible date ranges",
                )
        return None

    @staticmethod
    def _similar_subject(left: str, right: str) -> bool:
        normalize = lambda value: set(re.findall(r"[a-z0-9]+", value))
        stopwords = {"a", "an", "the", "by", "of", "for", "in", "on", "to", "with", "and", "was", "were", "is", "are"}
        left_tokens = normalize(left) - stopwords
        right_tokens = normalize(right) - stopwords
        if not left_tokens or not right_tokens:
            return False
        overlap = len(left_tokens & right_tokens)
        return overlap >= 2 or left_tokens == right_tokens

    @staticmethod
    def _same_subject(left: str, right: str) -> bool:
        normalize = lambda value: set(re.findall(r"[a-z0-9]+", value))
        left_tokens = normalize(left)
        right_tokens = normalize(right)
        return bool(left_tokens and right_tokens and (left_tokens == right_tokens or left_tokens & right_tokens))

    @staticmethod
    def _temporal_subject(value: str) -> str | None:
        match = _EMPLOYMENT_SUBJECT.search(value) or _EDUCATION_SUBJECT.search(value)
        if match:
            return match.group(1).strip()
        return None

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
        # An inferred quantified outcome/certification is not admissible without explicit evidence.
        # Unknown or partially-supported claims remain in the ledger so downstream consumers can
        # surface them as material gaps instead of losing the uncertainty during validation.
        if (_QUANTIFIED.search(claim.claim) or _CERTIFICATION.search(claim.claim)) and claim.kind is EvidenceKind.INFERRED:
            raise ValueError("Quantified outcomes and certifications require explicit evidence")
