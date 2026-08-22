from __future__ import annotations

import re

from career_os.models.evidence import EvidenceClaim, EvidenceLedger, SupportStatus
from career_os.models.fit import FitScore, RequirementEvaluation, RequirementStatus
from career_os.models.jd import JDAnalysis

_STOPWORDS = {
    "and", "the", "with", "for", "from", "that", "this", "have", "has", "years",
    "year", "using", "use", "ability", "strong", "good", "work", "working", "role",
}


def _terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#.-]+", text.casefold())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _evidence_match(requirement: str, claims: tuple[EvidenceClaim, ...]) -> RequirementEvaluation:
    required = _terms(requirement)
    if not required:
        return RequirementEvaluation(requirement, RequirementStatus.MISSING)

    candidates: list[tuple[EvidenceClaim, float]] = []
    for claim in claims:
        if claim.support not in {SupportStatus.SUPPORTED, SupportStatus.PARTIALLY_SUPPORTED}:
            continue
        overlap = required.intersection(_terms(claim.claim))
        if overlap:
            candidates.append((claim, len(overlap) / len(required)))

    if not candidates:
        return RequirementEvaluation(requirement, RequirementStatus.MISSING)

    candidates.sort(key=lambda item: (item[1], item[0].confidence), reverse=True)
    best_claim, coverage = candidates[0]
    status = RequirementStatus.MATCHED if coverage >= 0.6 else RequirementStatus.PARTIALLY_MATCHED
    return RequirementEvaluation(
        requirement=requirement,
        status=status,
        evidence_claim_ids=tuple(claim.claim_id for claim, _ in candidates[:3]),
        confidence=min(1.0, coverage * best_claim.confidence),
    )


class FitScorer:
    """Deterministically scores JD requirements against an evidence ledger."""

    name = "fit_scorer"

    def score(self, jd: JDAnalysis, ledger: EvidenceLedger) -> FitScore:
        claims = ledger.claims
        hard = tuple(_evidence_match(req, claims) for req in jd.must_have_requirements)
        preferred = tuple(_evidence_match(req, claims) for req in jd.preferred_requirements)
        skills = tuple(_evidence_match(skill, claims) for skill in jd.skills)

        def component(evaluations: tuple[RequirementEvaluation, ...]) -> float:
            if not evaluations:
                return 100.0
            values = {
                RequirementStatus.MATCHED: 1.0,
                RequirementStatus.PARTIALLY_MATCHED: 0.5,
                RequirementStatus.MISSING: 0.0,
            }
            return round(100.0 * sum(values[e.status] for e in evaluations) / len(evaluations), 2)

        hard_score = component(hard)
        preferred_score = component(preferred)
        skill_score = component(skills)
        overall = round(hard_score * 0.60 + preferred_score * 0.20 + skill_score * 0.20, 2)

        hard_gaps = tuple(e.requirement for e in hard if e.status is not RequirementStatus.MATCHED)
        preferred_gaps = tuple(e.requirement for e in preferred if e.status is RequirementStatus.MISSING)
        evidence_ids = tuple(
            dict.fromkeys(
                claim_id
                for evaluation in (*hard, *preferred, *skills)
                for claim_id in evaluation.evidence_claim_ids
            )
        )

        if hard_gaps:
            recommendation = "hard_gap"
        elif overall >= 80:
            recommendation = "strong_fit"
        elif overall >= 60:
            recommendation = "moderate_fit"
        else:
            recommendation = "weak_fit"

        return FitScore(
            overall=overall,
            hard_requirements=hard_score,
            preferred_requirements=preferred_score,
            skills=skill_score,
            hard_gaps=hard_gaps,
            preferred_gaps=preferred_gaps,
            evidence_claim_ids=evidence_ids,
            recommendation=recommendation,
        )
