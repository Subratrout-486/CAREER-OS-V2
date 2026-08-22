from __future__ import annotations

import re
from collections.abc import Iterable

from career_os.models.evidence import (
    EvidenceClaim,
    EvidenceKind,
    EvidenceLedger,
    EvidenceSource,
    SupportStatus,
)


class EvidenceAgent:
    """Builds a conservative evidence ledger from supplied candidate facts.

    The agent never upgrades a claim beyond the evidence supplied to it. It is
    intentionally deterministic so downstream scoring can audit every claim.
    """

    name = "evidence_agent"

    def build_ledger(
        self,
        facts: Iterable[dict[str, object]],
        *,
        source_id: str = "candidate-profile",
        source_type: str = "candidate_profile",
        source_label: str = "Candidate profile",
    ) -> EvidenceLedger:
        source = EvidenceSource(source_id=source_id, source_type=source_type, label=source_label)
        ledger = EvidenceLedger()
        for index, fact in enumerate(facts, start=1):
            claim = str(fact.get("claim", "")).strip()
            if not claim:
                continue
            kind = EvidenceKind(str(fact.get("kind", EvidenceKind.USER_PROVIDED.value)))
            support = SupportStatus(str(fact.get("support", SupportStatus.SUPPORTED.value)))
            confidence = float(fact.get("confidence", 0.8 if kind is EvidenceKind.VERIFIED else 0.6))
            claim_source = source if kind is EvidenceKind.VERIFIED else (
                source if fact.get("source_id") else None
            )
            ledger = ledger.add(
                EvidenceClaim(
                    claim_id=str(fact.get("claim_id", f"claim-{index}")),
                    claim=claim,
                    kind=kind,
                    support=support,
                    confidence=confidence,
                    source=claim_source,
                    notes=str(fact["notes"]) if fact.get("notes") is not None else None,
                )
            )
        return ledger

    def claims_for_requirement(self, ledger: EvidenceLedger, requirement: str) -> tuple[EvidenceClaim, ...]:
        terms = {term for term in re.findall(r"[a-z0-9+#.-]+", requirement.casefold()) if len(term) > 2}
        if not terms:
            return ()
        return tuple(
            claim for claim in ledger.claims
            if terms.intersection(re.findall(r"[a-z0-9+#.-]+", claim.claim.casefold()))
            and claim.support in {SupportStatus.SUPPORTED, SupportStatus.PARTIALLY_SUPPORTED}
        )
