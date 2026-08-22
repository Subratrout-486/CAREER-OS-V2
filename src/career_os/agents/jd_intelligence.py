from __future__ import annotations

import re
from collections.abc import Iterable

from career_os.models.jd import JDAnalysis


_SECTION_ALIASES = {
    "responsibilities": {"responsibilities", "what you'll do", "what you will do", "duties", "role responsibilities"},
    "must": {"requirements", "required qualifications", "must have", "qualifications", "what you bring"},
    "preferred": {"preferred qualifications", "preferred", "nice to have", "desired qualifications"},
}

_SKILLS = (
    "python", "sql", "power bi", "tableau", "excel", "java", "javascript", "typescript",
    "aws", "azure", "gcp", "oracle", "postgresql", "mysql", "snowflake", "servicenow",
    "rest api", "rest apis", "json", "xml", "etl", "jira", "salesforce", "sap", "workday",
)

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

        skills = _unique(skill for skill in _SKILLS if skill in lower)
        domains = _unique(term for term in _DOMAIN_TERMS if re.search(rf"\b{re.escape(term)}\b", lower))

        seniority = next(
            (level for level in ("intern", "entry", "junior", "associate", "mid", "senior", "lead", "manager", "director")
             if re.search(rf"\b{level}\b", lower)),
            None,
        )
        work_model = next((model for model in ("remote", "hybrid", "onsite", "on-site") if model in lower), None)

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
        if "responsibilities" not in lower and not responsibilities:
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
