from __future__ import annotations

import re
from dataclasses import dataclass

from career_os.models.jd import JDAnalysis


@dataclass(frozen=True)
class _Section:
    name: str
    lines: tuple[str, ...]


class JDAnalyzer:
    """Deterministic first-pass JD parser.

    The parser deliberately separates extraction from inference. It preserves
    source wording, uses bounded skill matching, and records ambiguity instead
    of inventing missing information. An LLM can enrich the resulting model
    later without becoming the source of truth for deterministic fields.
    """

    _HEADINGS = {
        "responsibilities": {"responsibilities", "what you will do", "what you'll do", "duties", "role responsibilities"},
        "required": {"requirements", "required qualifications", "qualifications", "must have", "what you bring", "basic qualifications"},
        "preferred": {"preferred qualifications", "preferred", "nice to have", "nice-to-have", "desired qualifications"},
        "benefits": {"benefits", "what we offer", "perks"},
    }
    _ALIASES = {
        "python": {"python"},
        "sql": {"sql", "structured query language"},
        "power bi": {"power bi", "powerbi"},
        "tableau": {"tableau"},
        "excel": {"excel", "microsoft excel"},
        "aws": {"aws", "amazon web services"},
        "rest apis": {"rest api", "rest apis", "restful api", "restful apis"},
        "json": {"json"},
        "oracle": {"oracle database", "oracle db", "oracle"},
        "pl/sql": {"pl/sql", "plsql"},
        "unix": {"unix", "unix/linux"},
        "serviceNow": {"servicenow", "service now"},
        "control-m": {"control-m", "control m"},
        "jira": {"jira"},
        "salesforce": {"salesforce"},
        "customer success": {"customer success"},
        "project management": {"project management"},
        "data analysis": {"data analysis", "data analytics"},
    }
    _SENIORITY = ("Intern", "Entry Level", "Junior", "Associate", "Mid-Level", "Mid Level", "Senior", "Lead", "Principal", "Staff", "Manager", "Director", "Head", "VP", "Vice President")
    _WORK_MODELS = ("remote", "hybrid", "on-site", "onsite", "on site")
    _LOCATION_RE = re.compile(r"\b(?:location|based in|office in|job location)\s*[:\-]?\s*([^\n]+)", re.I)
    _COMP_RE = re.compile(r"(?:\$|₹|€|£)\s?[\d,]+(?:\.\d+)?(?:\s*[-–]\s*(?:\$|₹|€|£)?\s?[\d,]+(?:\.\d+)?)?(?:\s*(?:per year|annually|/year|per annum|per hour|/hour))?", re.I)
    _EXP_RE = re.compile(r"\b(?:at least\s+)?(\d+)\+?\s+years?\b", re.I)

    def analyze(self, source_text: str) -> JDAnalysis:
        if not source_text or not source_text.strip():
            raise ValueError("source_text must not be empty")
        text = source_text.replace("\r\n", "\n").replace("\r", "\n")
        sections = self._sections(text)
        responsibilities = self._bullets(self._section_lines(sections, "responsibilities"))
        required = self._bullets(self._section_lines(sections, "required"))
        preferred = self._bullets(self._section_lines(sections, "preferred"))
        skill_source = "\n".join([*required, *preferred, *responsibilities, text])
        skills = self._skills(skill_source)
        seniority = self._first_match(text, self._SENIORITY)
        work_model = self._first_match(text, self._WORK_MODELS)
        location_match = self._LOCATION_RE.search(text)
        compensation_match = self._COMP_RE.search(text)

        explicit = [*required, *preferred]
        ambiguities: list[str] = []
        if not sections:
            ambiguities.append("No recognizable section headings; classification is based on whole-document signals.")
        if not location_match:
            ambiguities.append("Location is not explicitly stated in a recognizable location field.")
        if not compensation_match:
            ambiguities.append("Compensation is not explicitly stated.")
        if not seniority:
            ambiguities.append("Seniority is not explicitly stated.")

        inferred: list[str] = []
        if "senior" in (seniority or "").lower() and not self._EXP_RE.search(text):
            ambiguities.append("Senior-level signal is present without an explicit years-of-experience requirement.")
        if "remote" in text.lower() and not work_model:
            ambiguities.append("Remote signal found but work-model classification is ambiguous.")

        return JDAnalysis(
            source_text=text,
            responsibilities=responsibilities,
            must_have_requirements=required,
            preferred_requirements=preferred,
            skills=skills,
            domain_terms=[],
            seniority=seniority,
            location=location_match.group(1).strip() if location_match else None,
            work_model=work_model,
            compensation=compensation_match.group(0) if compensation_match else None,
            explicit_signals=explicit,
            inferred_signals=inferred,
            ambiguities=ambiguities,
        )

    def _sections(self, text: str) -> list[_Section]:
        current: str | None = None
        buckets: dict[str, list[str]] = {}
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            normalized = re.sub(r"[^a-z0-9\- ]", "", line.lower()).strip()
            heading = next((key for key, values in self._HEADINGS.items() if normalized in values), None)
            if heading:
                current = heading
                buckets.setdefault(heading, [])
                continue
            if current:
                buckets[current].append(line)
        return [_Section(name, tuple(lines)) for name, lines in buckets.items()]

    @staticmethod
    def _section_lines(sections: list[_Section], name: str) -> list[str]:
        for section in sections:
            if section.name == name:
                return list(section.lines)
        return []

    @staticmethod
    def _bullets(lines: list[str]) -> list[str]:
        result: list[str] = []
        for line in lines:
            clean = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
            if clean and clean not in result:
                result.append(clean)
        return result

    def _skills(self, text: str) -> list[str]:
        lowered = text.lower()
        found: list[str] = []
        for canonical, aliases in self._ALIASES.items():
            if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lowered) for alias in aliases):
                found.append(canonical)
        return found

    @staticmethod
    def _first_match(text: str, choices: tuple[str, ...]) -> str | None:
        lowered = text.lower()
        matches = [(lowered.find(choice.lower()), choice) for choice in choices if choice.lower() in lowered]
        return min(matches)[1] if matches else None
