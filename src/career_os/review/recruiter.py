from __future__ import annotations

from dataclasses import dataclass
import re

from career_os.audit.ats import ATSAudit
from career_os.models.jd import JDAnalysis
from career_os.models.resume import TailoredResume


@dataclass(frozen=True)
class RecruiterFinding:
    severity: str
    category: str
    message: str
    evidence: tuple[str, ...] = ()
    recommendation: str | None = None


@dataclass(frozen=True)
class RecruiterReview:
    findings: tuple[RecruiterFinding, ...]
    shortlist_reasons: tuple[str, ...]
    recommendation: str
    confidence: str

    @property
    def passed(self) -> bool:
        return self.recommendation in {"shortlist", "review"} and not any(
            f.severity == "critical" for f in self.findings
        )


def _contains(text: str, term: str) -> bool:
    return bool(term.strip()) and re.search(rf"(?<!\w){re.escape(term.strip())}(?!\w)", text, re.I) is not None


def review_candidate(
    resume: TailoredResume,
    jd: JDAnalysis,
    ats: ATSAudit | None = None,
) -> RecruiterReview:
    """Review a candidate package using only supplied resume/JD/audit evidence."""
    resume_text = " ".join(
        [resume.summary, *(b.text for b in resume.bullets), *resume.matched_keywords]
    )
    findings: list[RecruiterFinding] = []
    reasons: list[str] = []

    missing_must = tuple(term for term in jd.must_have_requirements if not _contains(resume_text, term))
    if missing_must:
        findings.append(
            RecruiterFinding(
                "critical",
                "qualification-gap",
                "A material required qualification is not evidenced.",
                missing_must,
                "Treat the requirement as a genuine gap; do not infer it from adjacent experience.",
            )
        )
    else:
        reasons.append("All explicitly required JD terms are evidenced in the tailored resume.")

    if jd.preferred_requirements:
        preferred = tuple(term for term in jd.preferred_requirements if _contains(resume_text, term))
        if preferred:
            reasons.append(f"Preferred requirements evidenced: {', '.join(preferred)}.")
        missing_preferred = tuple(term for term in jd.preferred_requirements if term not in preferred)
        if missing_preferred:
            findings.append(
                RecruiterFinding(
                    "low",
                    "preferred-gap",
                    "Some preferred requirements are not evidenced.",
                    missing_preferred,
                    "Leave these as gaps unless the candidate can provide evidence.",
                )
            )

    unlinked = tuple(b.text for b in resume.bullets if not b.evidence_claim_ids)
    if unlinked:
        findings.append(
            RecruiterFinding(
                "high",
                "credibility",
                "Some resume bullets lack linked evidence claims.",
                unlinked,
                "Link the claims to verified evidence or remove them.",
            )
        )

    if resume.omitted_claim_ids:
        reasons.append(f"{len(resume.omitted_claim_ids)} unsupported claims were intentionally omitted.")

    if ats and any(f.severity == "error" for f in ats.findings):
        findings.append(
            RecruiterFinding(
                "critical",
                "ats-risk",
                "The ATS audit contains material errors that a recruiter may encounter during screening.",
                tuple(f.message for f in ats.findings if f.severity == "error"),
                "Resolve the underlying qualification or structure issue before submission.",
            )
        )

    contradictions = []
    for term in jd.must_have_requirements:
        if _contains(jd.source_text, f"no {term}") and _contains(resume_text, term):
            contradictions.append(term)
    if contradictions:
        findings.append(
            RecruiterFinding(
                "critical",
                "contradiction",
                "Resume evidence conflicts with explicit JD wording.",
                tuple(contradictions),
                "Review the source JD and resume evidence manually before proceeding.",
            )
        )

    critical = any(f.severity == "critical" for f in findings)
    high = any(f.severity == "high" for f in findings)
    if critical:
        recommendation, confidence = "review", "low"
    elif high:
        recommendation, confidence = "review", "medium"
    elif reasons:
        recommendation, confidence = "shortlist", "medium"
    else:
        recommendation, confidence = "review", "low"

    return RecruiterReview(tuple(findings), tuple(reasons), recommendation, confidence)
