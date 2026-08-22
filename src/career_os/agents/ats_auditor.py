from __future__ import annotations

import re

from career_os.models.ats import ATSAudit, ATSFinding, ATSSeverity
from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeProfile

_STOPWORDS = {
    "and", "the", "with", "for", "from", "that", "this", "have", "has", "years",
    "year", "using", "use", "ability", "strong", "good", "work", "working", "role",
}


def _terms(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9+#.-]+", text.casefold())
        if len(token) > 2 and token not in _STOPWORDS
    }


class ATSAuditor:
    """Runs deterministic, explainable ATS checks on a structured resume draft."""

    name = "ats_auditor"

    def audit(self, resume: ResumeProfile, jd: JDAnalysis | None = None) -> ATSAudit:
        findings: list[ATSFinding] = []
        text = " ".join([resume.summary, *(bullet.text for bullet in resume.bullets)])
        terms = _terms(text)

        if not resume.summary.strip():
            findings.append(ATSFinding("missing_summary", ATSSeverity.MEDIUM, "Resume summary is empty."))
        if not resume.bullets:
            findings.append(ATSFinding("missing_experience", ATSSeverity.HIGH, "No experience bullets are present."))
        if any(len(bullet.text.split()) > 45 for bullet in resume.bullets):
            findings.append(ATSFinding("long_bullet", ATSSeverity.MEDIUM, "At least one bullet is unusually long and may reduce scanability."))
        if re.search(r"[^\x00-\x7f]", text):
            findings.append(ATSFinding("non_ascii_text", ATSSeverity.LOW, "Non-ASCII characters are present; verify parser-safe rendering."))

        matched: set[str] = set()
        missing: set[str] = set()
        if jd is not None:
            jd_terms = _terms(" ".join((*jd.must_have_requirements, *jd.preferred_requirements, *jd.skills)))
            matched = terms.intersection(jd_terms)
            missing = jd_terms - terms
            if missing:
                findings.append(
                    ATSFinding(
                        "missing_keywords",
                        ATSSeverity.MEDIUM,
                        f"{len(missing)} target keywords are not present in the structured resume text.",
                    )
                )

        score = 100.0
        penalties = {
            ATSSeverity.CRITICAL: 30.0,
            ATSSeverity.HIGH: 20.0,
            ATSSeverity.MEDIUM: 10.0,
            ATSSeverity.LOW: 3.0,
        }
        for finding in findings:
            score -= penalties[finding.severity]
        if jd is not None:
            target = matched | missing
            if target:
                score -= 30.0 * (len(missing) / len(target))
        return ATSAudit(
            score=round(max(0.0, min(100.0, score)), 2),
            findings=tuple(findings),
            matched_keywords=tuple(sorted(matched)),
            missing_keywords=tuple(sorted(missing)),
        )
