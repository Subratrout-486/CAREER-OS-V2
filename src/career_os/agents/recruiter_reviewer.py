from __future__ import annotations

import re

from career_os.models.evidence import EvidenceLedger, SupportStatus
from career_os.models.fit import FitScore
from career_os.models.jd import JDAnalysis
from career_os.models.resume import TailoredResume
from career_os.models.recruiter_review import RecruiterReview


def _terms(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9+#.-]+", text.casefold()) if len(t) > 2}


class RecruiterReviewer:
    """Produces an auditable recruiter-style review from upstream artifacts."""

    name = "recruiter_reviewer"

    def review(self, jd: JDAnalysis, resume: TailoredResume, fit: FitScore, evidence: EvidenceLedger) -> RecruiterReview:
        supported = {c.claim_id for c in evidence.claims if c.support in {SupportStatus.SUPPORTED, SupportStatus.PARTIALLY_SUPPORTED}}
        strengths: list[str] = []
        objections: list[str] = []
        risks: list[str] = []
        fixes: list[str] = []

        if fit.overall >= 80 and not fit.hard_gaps:
            strengths.append("Strong alignment with the structured job requirements.")
        elif fit.overall >= 60:
            strengths.append("Meaningful alignment, with some gaps a recruiter should review.")
        else:
            objections.append("Overall fit is weak based on the evidence-backed score.")

        objections.extend(f"Missing hard requirement: {gap}" for gap in fit.hard_gaps)
        fixes.extend(f"Address or contextualize preferred gap: {gap}" for gap in fit.preferred_gaps)

        resume_claim_ids = {cid for bullet in resume.bullets for cid in bullet.evidence_claim_ids}
        if resume_claim_ids - supported:
            risks.append("Resume contains claim references that are not supported by the evidence ledger.")

        jd_terms = _terms(" ".join((*jd.must_have_requirements, *jd.preferred_requirements, *jd.skills)))
        resume_terms = _terms(" ".join([resume.summary, *(b.text for b in resume.bullets)]))
        missing = sorted(jd_terms - resume_terms)
        if missing:
            fixes.append("Consider whether these missing JD terms are genuinely applicable: " + ", ".join(missing[:8]) + ".")

        if not resume.bullets:
            risks.append("No resume bullets are available for recruiter review.")

        if fit.recommendation == "hard_gap":
            recommendation = "do_not_shortlist"
        elif risks:
            recommendation = "manual_review"
        elif fit.overall >= 80:
            recommendation = "shortlist"
        else:
            recommendation = "manual_review"

        return RecruiterReview(
            recommendation=recommendation,
            strengths=tuple(strengths),
            objections=tuple(objections),
            risks=tuple(risks),
            fixes=tuple(fixes),
            evidence_claim_ids=tuple(sorted(supported.intersection(resume_claim_ids))),
        )
