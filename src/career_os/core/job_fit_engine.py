from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from career_os.models.fit import FitScore, RequirementEvaluation, RequirementStatus
from career_os.models.jd import JDAnalysis


@dataclass(frozen=True)
class CandidateProfile:
    """Evidence-backed candidate facts used for deterministic fit scoring."""

    skills: frozenset[str] = frozenset()
    experience_terms: frozenset[str] = frozenset()
    education_terms: frozenset[str] = frozenset()
    locations: frozenset[str] = frozenset()


def _norm(value: str) -> str:
    return " ".join(value.casefold().replace("/", " ").replace("-", " ").split())


def _matched(requirement: str, evidence: Iterable[str]) -> bool:
    req = _norm(requirement)
    return any(req == _norm(item) or req in _norm(item) or _norm(item) in req for item in evidence)


class JobFitEngine:
    """Score a JD against explicit candidate evidence without inventing experience."""

    def evaluate(self, jd: JDAnalysis, profile: CandidateProfile) -> tuple[FitScore, list[RequirementEvaluation]]:
        evaluations: list[RequirementEvaluation] = []
        hard_gaps: list[str] = []
        preferred_gaps: list[str] = []
        matched_hard = 0
        matched_preferred = 0
        evidence = profile.skills | profile.experience_terms | profile.education_terms

        for requirement in jd.must_have_requirements:
            ok = _matched(requirement, evidence)
            status = RequirementStatus.MATCHED if ok else RequirementStatus.MISSING
            if ok:
                matched_hard += 1
            else:
                hard_gaps.append(requirement)
            evaluations.append(RequirementEvaluation(requirement, status, confidence=1.0 if ok else 0.0))

        for requirement in jd.preferred_requirements:
            ok = _matched(requirement, evidence)
            status = RequirementStatus.MATCHED if ok else RequirementStatus.MISSING
            if ok:
                matched_preferred += 1
            else:
                preferred_gaps.append(requirement)
            evaluations.append(RequirementEvaluation(requirement, status, confidence=1.0 if ok else 0.0))

        hard_total = len(jd.must_have_requirements)
        preferred_total = len(jd.preferred_requirements)
        hard_score = 100.0 if not hard_total else 100.0 * matched_hard / hard_total
        preferred_score = 100.0 if not preferred_total else 100.0 * matched_preferred / preferred_total
        skill_hits = sum(1 for skill in jd.skills if _matched(skill, profile.skills))
        skill_score = 100.0 if not jd.skills else 100.0 * skill_hits / len(jd.skills)

        overall = 0.60 * hard_score + 0.20 * preferred_score + 0.20 * skill_score
        if hard_gaps:
            recommendation = "review_required" if hard_score >= 70.0 else "weak_fit"
        elif overall >= 80.0:
            recommendation = "strong_fit"
        elif overall >= 65.0:
            recommendation = "good_fit"
        else:
            recommendation = "review_required"

        return FitScore(
            overall=round(overall, 2),
            hard_requirements=round(hard_score, 2),
            preferred_requirements=round(preferred_score, 2),
            skills=round(skill_score, 2),
            hard_gaps=tuple(hard_gaps),
            preferred_gaps=tuple(preferred_gaps),
            recommendation=recommendation,
        ), evaluations
