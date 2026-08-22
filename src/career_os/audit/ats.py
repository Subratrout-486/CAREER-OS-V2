from __future__ import annotations

from dataclasses import dataclass
import re

from career_os.models.jd import JDAnalysis
from career_os.models.resume import TailoredResume


@dataclass(frozen=True)
class ATSFinding:
    severity: str
    category: str
    message: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class ATSAudit:
    findings: tuple[ATSFinding, ...]
    matched_requirements: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    keyword_coverage: float

    @property
    def passed(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)


_ALIASES = {
    "powerbi": "power bi",
    "restful api": "rest api",
    "restful apis": "rest api",
    "postgres": "postgresql",
    "amazon web services": "aws",
    "microsoft azure": "azure",
    "google cloud platform": "gcp",
}


def _normalize(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.casefold().replace("&", " and ")).strip()
    return _ALIASES.get(normalized, normalized)


def _contains(text: str, term: str) -> bool:
    normalized_text = _normalize(text)
    normalized_term = _normalize(term)
    if not normalized_term:
        return False
    return normalized_term in normalized_text


def audit_resume(resume: TailoredResume, jd: JDAnalysis) -> ATSAudit:
    """Run a deterministic ATS/readability audit against structured JD evidence."""
    resume_text = " ".join(
        [resume.summary, *(bullet.text for bullet in resume.bullets), *resume.matched_keywords]
    )
    findings: list[ATSFinding] = []

    if not resume.summary.strip():
        findings.append(ATSFinding("error", "structure", "Resume summary is empty."))
    if not resume.bullets:
        findings.append(ATSFinding("error", "structure", "Resume contains no experience bullets."))
    if any(not bullet.text.strip() for bullet in resume.bullets):
        findings.append(ATSFinding("error", "structure", "Resume contains an empty bullet."))
    if any(not bullet.evidence_claim_ids for bullet in resume.bullets):
        findings.append(
            ATSFinding("warning", "provenance", "At least one bullet has no linked evidence claim.")
        )

    all_requirements = [*jd.must_have_requirements, *jd.preferred_requirements, *jd.skills]
    matched = tuple(term for term in all_requirements if _contains(resume_text, term))
    missing = tuple(term for term in all_requirements if term not in matched)

    must_missing = tuple(term for term in jd.must_have_requirements if term in missing)
    if must_missing:
        findings.append(
            ATSFinding(
                "error",
                "qualification-gap",
                "Required JD terms are not evidenced in the resume.",
                must_missing,
            )
        )
    if jd.preferred_requirements:
        preferred_missing = tuple(term for term in jd.preferred_requirements if term in missing)
        if preferred_missing:
            findings.append(
                ATSFinding(
                    "warning",
                    "qualification-gap",
                    "Preferred JD terms are not evidenced in the resume.",
                    preferred_missing,
                )
            )

    coverage = len(matched) / len(all_requirements) if all_requirements else 1.0
    if coverage < 0.5 and all_requirements:
        findings.append(
            ATSFinding(
                "warning",
                "keyword-coverage",
                "Less than half of the structured JD terms are evidenced.",
            )
        )

    return ATSAudit(findings, matched, missing, coverage)
