from __future__ import annotations

import re

from career_os.models.evidence import EvidenceClaim, EvidenceLedger, SupportStatus
from career_os.models.fit import FitScore, RequirementEvaluation, RequirementStatus
from career_os.models.jd import JDAnalysis

_STOPWORDS = {"and", "the", "with", "for", "from", "that", "this", "have", "has", "years", "year", "using", "use", "ability", "strong", "good", "work", "working", "role", "basic", "understanding", "knowledge", "familiarity", "experience", "required", "discipline", "equivalent"}
_ALIASES = {
    "powerbi": "power bi", "power-bi": "power bi", "restful api": "rest api", "restful apis": "rest api",
    "postgres": "postgresql", "postgres db": "postgresql", "amazon web services": "aws",
    "microsoft azure": "azure", "google cloud platform": "gcp", "unix/linux": "unix", "linux/unix": "unix",
}

_TECHNICAL_ALIASES = {
    "sql": ("sql",), "unix": ("unix", "linux", "unix/linux", "linux/unix"), "ftp/sftp": ("ftp", "sftp", "file transfer"),
    "cloud computing": ("cloud computing", "cloud infrastructure", "cloud setup", "vm", "vms", "networking fundamentals"),
    "python": ("python",), "aws": ("aws", "amazon web services"), "azure": ("azure", "microsoft azure"),
    "gcp": ("gcp", "google cloud platform"), "oracle": ("oracle",), "servicenow": ("servicenow", "service now"),
    "salesforce": ("salesforce",), "jira": ("jira",), "rest api": ("rest api", "rest apis", "restful api", "restful apis"),
}

# Education detection requires degree context so domain terms such as
# "Master Data Management" remain ordinary job requirements.
_EDUCATION_PATTERNS = (
    r"\b(?:bachelor(?:'s|s)?|phd|doctorate|b\.?tech|b\.?sc|b\.?com|m\.?tech|m\.?sc|m\.?com|mba)\b",
    r"\bb\.?e\.?\s+degree\b",
    r"\bm\.?e\.?\s+degree\b",
    r"\bmaster(?:'s|s)?\s+(?:degree|of|in)\b",
    r"\b(?:associate|undergraduate|graduate)\s+degree\b",
    r"\bengineering\s+degree\b",
    r"\bcomputer\s+science\s+degree\b",
)

_EDUCATION_FAMILIES = (
    ("btech", "bachelor", (r"\bb\.?tech\b", r"\bbachelor(?:'s|s)?\s+of\s+technology\b")),
    ("be", "bachelor", (r"\bb\.?e\.?\s+degree\b", r"\bbachelor(?:'s|s)?\s+of\s+engineering\b")),
    ("bcom", "bachelor", (r"\bb\.?com\b", r"\bbachelor(?:'s|s)?\s+of\s+commerce\b")),
    ("bsc", "bachelor", (r"\bb\.?sc\b", r"\bbachelor(?:'s|s)?\s+of\s+science\b")),
    ("mtech", "master", (r"\bm\.?tech\b", r"\bmaster(?:'s|s)?\s+of\s+technology\b")),
    ("me", "master", (r"\bm\.?e\.?\s+degree\b", r"\bmaster(?:'s|s)?\s+of\s+engineering\b")),
    ("mcom", "master", (r"\bm\.?com\b", r"\bmaster(?:'s|s)?\s+of\s+commerce\b")),
    ("msc", "master", (r"\bm\.?sc\b", r"\bmaster(?:'s|s)?\s+of\s+science\b")),
    ("mba", "master", (r"\bmba\b", r"\bmaster(?:'s|s)?\s+of\s+business\s+administration\b")),
    ("bachelor", "bachelor", (r"\bbachelor(?:'s|s)?\b",)),
    ("master", "master", (r"\bmaster(?:'s|s)?\s+(?:degree|of|in)\b",)),
    ("undergraduate", "bachelor", (r"\bundergraduate\s+degree\b",)),
    ("engineering", "bachelor", (r"\bengineering\s+degree\b",)),
    ("computer_science", "bachelor", (r"\bcomputer\s+science\s+degree\b",)),
    ("postgraduate", "postgraduate", (r"\bgraduate\s+degree\b", r"\bpostgraduate\b")),
    ("associate", "associate", (r"\bassociate\s+degree\b",)),
    ("phd", "phd", (r"\bphd\b", r"\bdoctorate\b")),
)


def _canonical_text(text: str) -> str:
    """Normalize aliases and casing before requirement matching."""
    value = text.casefold()
    for alias, canonical in sorted(_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        value = re.sub(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", canonical, value)
    return value


def _terms(text: str) -> set[str]:
    """Return normalized, non-stopword terms for conservative overlap matching."""
    return {token for token in re.findall(r"[a-z0-9+#.-]+", _canonical_text(text)) if len(token) > 2 and token not in _STOPWORDS}


def _is_education_requirement(requirement: str) -> bool:
    """Identify education requirements without confusing domain terms with degrees."""
    low = _canonical_text(requirement)
    return any(re.search(pattern, low) for pattern in _EDUCATION_PATTERNS)


def _education_descriptor(text: str) -> tuple[str | None, str | None]:
    """Return (specific family, education level) for an explicitly stated degree."""
    low = _canonical_text(text)
    for family, level, patterns in _EDUCATION_FAMILIES:
        if any(re.search(pattern, low) for pattern in patterns):
            return family, level
    return None, None


def _education_matches(requirement: str, claim: str) -> bool:
    """Match education requirements by exact family when specific, or by level when generic."""
    required_family, required_level = _education_descriptor(requirement)
    claim_family, claim_level = _education_descriptor(claim)
    if not required_level or not claim_level or required_level != claim_level:
        return False
    if required_family in {"bachelor", "master", "postgraduate", "associate", "phd"}:
        return True
    return required_family == claim_family


def _focused_terms(requirement: str) -> set[str]:
    """Extract semantic matching keys for objective non-education requirements."""
    low = _canonical_text(requirement)
    focused: set[str] = set()
    for canonical, aliases in _TECHNICAL_ALIASES.items():
        if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", low) for alias in aliases):
            focused.add(canonical)
    if focused:
        return focused
    if re.search(r"\bbachelor(?:'s)?\b", low):
        return {"bachelor"}
    if re.search(r"\b(?:1|2|3|4|5|6|7|8|9|10)\s*[-–]\s*(?:1|2|3|4|5|6|7|8|9|10)\s+year", low) or "years of experience" in low or "years' experience" in low:
        return {"experience_years"}
    return _terms(requirement)


def _claim_supports_focus(claim: EvidenceClaim, focus: str) -> bool:
    """Check whether an evidence claim explicitly supports a focused requirement."""
    text = _canonical_text(claim.claim)
    if focus == "bachelor":
        return bool(re.search(r"\bbachelor(?:'s)?\b", text))
    if focus == "experience_years":
        return bool(re.search(r"\b(?:nearly\s+)?\d+(?:\.\d+)?\s*(?:years?|yrs?)\b", text, re.I))
    aliases = _TECHNICAL_ALIASES.get(focus, (focus,))
    return any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text) for alias in aliases)


def _evidence_match(requirement: str, claims: tuple[EvidenceClaim, ...]) -> RequirementEvaluation:
    """Match one requirement against supported evidence and return traceable results."""
    if _is_education_requirement(requirement):
        for claim in claims:
            if claim.support not in {SupportStatus.SUPPORTED, SupportStatus.PARTIALLY_SUPPORTED}:
                continue
            if _education_matches(requirement, claim.claim):
                return RequirementEvaluation(
                    requirement=requirement,
                    status=RequirementStatus.MATCHED,
                    evidence_claim_ids=(claim.claim_id,),
                    confidence=1.0,
                )
        return RequirementEvaluation(requirement, RequirementStatus.MISSING)

    required = _focused_terms(requirement)
    if not required:
        return RequirementEvaluation(requirement, RequirementStatus.MISSING)

    focused_candidates: list[tuple[EvidenceClaim, float]] = []
    for claim in claims:
        if claim.support not in {SupportStatus.SUPPORTED, SupportStatus.PARTIALLY_SUPPORTED}:
            continue
        if any(_claim_supports_focus(claim, focus) for focus in required):
            focused_candidates.append((claim, 1.0))

    if focused_candidates:
        return RequirementEvaluation(
            requirement=requirement,
            status=RequirementStatus.MATCHED,
            evidence_claim_ids=tuple(claim.claim_id for claim, _ in focused_candidates[:3]),
            confidence=1.0,
        )

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
    return RequirementEvaluation(requirement, status, tuple(claim.claim_id for claim, _ in candidates[:3]), min(1.0, coverage * best_claim.confidence))


class FitScorer:
    """Deterministically scores requirements; education is a visible risk, not a gate."""

    name = "fit_scorer"

    def score(self, jd: JDAnalysis, ledger: EvidenceLedger) -> FitScore:
        """Score hard, preferred, and skill requirements while isolating education risk."""
        claims = ledger.claims
        hard_all = tuple(_evidence_match(req, claims) for req in jd.must_have_requirements)
        preferred_all = tuple(_evidence_match(req, claims) for req in jd.preferred_requirements)
        skills = tuple(_evidence_match(skill, claims) for skill in jd.skills)

        education = tuple(e for e in (*hard_all, *preferred_all) if _is_education_requirement(e.requirement))
        hard = tuple(e for e in hard_all if not _is_education_requirement(e.requirement))
        preferred = tuple(e for e in preferred_all if not _is_education_requirement(e.requirement))

        def component(evaluations: tuple[RequirementEvaluation, ...]) -> float:
            """Calculate a normalized component score from requirement evaluations."""
            if not evaluations:
                return 100.0
            values = {RequirementStatus.MATCHED: 1.0, RequirementStatus.PARTIALLY_MATCHED: 0.5, RequirementStatus.MISSING: 0.0}
            return round(100.0 * sum(values[e.status] for e in evaluations) / len(evaluations), 2)

        hard_score = component(hard)
        preferred_score = component(preferred)
        skill_score = component(skills)
        overall = round(hard_score * 0.60 + preferred_score * 0.20 + skill_score * 0.20, 2)

        hard_gaps = tuple(e.requirement for e in hard if e.status is not RequirementStatus.MATCHED)
        preferred_gaps = tuple(e.requirement for e in preferred if e.status is RequirementStatus.MISSING)
        education_gaps = tuple(e.requirement for e in education if e.status is not RequirementStatus.MATCHED)
        education_risk = "mismatch" if education_gaps else "matched" if education else "not_stated"
        evidence_ids = tuple(dict.fromkeys(claim_id for evaluation in (*hard_all, *preferred_all, *skills) for claim_id in evaluation.evidence_claim_ids))
        recommendation = "hard_gap" if hard_gaps else ("strong_fit" if overall >= 80 else "moderate_fit" if overall >= 60 else "weak_fit")

        return FitScore(
            overall,
            hard_score,
            preferred_score,
            skill_score,
            hard_gaps,
            preferred_gaps,
            evidence_ids,
            recommendation,
            education_gaps,
            education_risk,
        )
