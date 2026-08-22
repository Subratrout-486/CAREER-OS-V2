from __future__ import annotations

import re
from collections.abc import Iterable

from career_os.models.jd import JDAnalysis


_SECTION_ALIASES = {
    "responsibilities": {
        "responsibilities", "key responsibilities", "what you'll do", "what you will do",
        "duties", "role responsibilities", "your responsibilities",
    },
    "must": {
        "requirements", "required qualifications", "basic qualifications", "minimum qualifications",
        "must have", "qualifications", "what you bring", "what you'll need", "what you will need",
    },
    "preferred": {
        "preferred qualifications", "preferred", "preferred skills", "nice to have", "desired qualifications",
        "bonus qualifications", "additional qualifications",
    },
}

_SKILL_ALIASES = {
    "python": ("python",),
    "sql": ("sql",),
    "power bi": ("power bi", "powerbi"),
    "tableau": ("tableau",),
    "excel": ("excel", "microsoft excel"),
    "java": ("java",),
    "javascript": ("javascript", "js"),
    "typescript": ("typescript",),
    "aws": ("aws", "amazon web services"),
    "azure": ("azure", "microsoft azure"),
    "gcp": ("gcp", "google cloud platform"),
    "oracle": ("oracle",),
    "postgresql": ("postgresql", "postgres"),
    "mysql": ("mysql",),
    "snowflake": ("snowflake",),
    "servicenow": ("servicenow", "service now"),
    "rest api": ("rest api", "rest apis", "restful api", "restful apis"),
    "json": ("json",),
    "xml": ("xml",),
    "etl": ("etl", "extract transform load"),
    "jira": ("jira",),
    "salesforce": ("salesforce",),
    "sap": ("sap",),
    "workday": ("workday",),
}

_DOMAIN_TERMS = (
    "analytics", "product", "customer success", "research", "finance", "banking", "saas",
    "risk", "compliance", "operations", "support", "data", "governance", "sales", "marketing",
)


def _clean_lines(text: str) -> list[str]:
    return [line.strip(" -•\t") for line in text.splitlines() if line.strip(" -•\t")]


def _sectioned(text: str) -> dict[str, list[str]]:
    sections = {key: [] for key in _SECTION_ALIASES}
    current: str | None = None
    for line in _clean_lines(text):
        heading = re.sub(r"[:#]+$", "", line).strip().casefold()
        matched = next((key for key, aliases in _SECTION_ALIASES.items() if heading in aliases), None)
        if matched:
            current = matched
            continue
        if current:
            sections[current].append(line)
    return sections


def _contains_term(text: str, term: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(term.casefold())}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


class JDIntelligence:
    """Deterministic first-pass JD analysis; preserves source wording and avoids guessing."""

    name = "jd_intelligence"

    def analyze(self, text: str) -> JDAnalysis:
        source = text.strip()
        if not source:
            raise ValueError("Job description cannot be empty")

        sections = _sectioned(source)
        lower = source.casefold()
        responsibilities = sections["responsibilities"]
        must = sections["must"]
        preferred = sections["preferred"]

        skills = [
            canonical
            for canonical, aliases in _SKILL_ALIASES.items()
            if any(_contains_term(lower, alias) for alias in aliases)
        ]
        skills = _unique(skills)
        domains = _unique(term for term in _DOMAIN_TERMS if _contains_term(lower, term))

        seniority = next(
            (level for level in ("intern", "entry", "junior", "associate", "mid", "senior", "lead", "manager", "director")
             if _contains_term(lower, level)),
            None,
        )
        work_model = next(
            (model for model in ("remote", "hybrid", "onsite", "on-site") if _contains_term(lower, model)),
            None,
        )

        location_match = re.search(r"(?:location|based in|office location)\s*[:\-]\s*([^\n]+)", source, re.I)
        compensation_match = re.search(r"(?:salary|compensation|pay range|range)\s*[:\-]?\s*([^\n]+)", source, re.I)

        explicit = []
        if seniority:
            explicit.append(f"seniority signal: {seniority}")
        if work_model:
            explicit.append(f"work model signal: {work_model}")
        if skills:
            explicit.append("skills explicitly mentioned in source")

        inferred = []
        if not responsibilities:
            inferred.append("responsibility section not explicitly labeled")

        ambiguities = []
        if not must:
            ambiguities.append("No clearly labeled required-qualification section found")
        if not preferred:
            ambiguities.append("No clearly labeled preferred-qualification section found")
        if not location_match:
            ambiguities.append("Location not explicitly labeled")
        if not compensation_match:
            ambiguities.append("Compensation not explicitly stated")

        return JDAnalysis(
            source_text=source,
            responsibilities=_unique(responsibilities),
            must_have_requirements=_unique(must),
            preferred_requirements=_unique(preferred),
            skills=skills,
            domain_terms=domains,
            seniority=seniority,
            location=location_match.group(1).strip() if location_match else None,
            work_model=work_model,
            compensation=compensation_match.group(1).strip() if compensation_match else None,
            explicit_signals=explicit,
            inferred_signals=inferred,
            ambiguities=ambiguities,
        )
