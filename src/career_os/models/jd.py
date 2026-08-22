from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class JDAnalysis:
    """Normalized, auditable analysis of a job description."""

    source_text: str
    responsibilities: list[str] = field(default_factory=list)
    must_have_requirements: list[str] = field(default_factory=list)
    preferred_requirements: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    domain_terms: list[str] = field(default_factory=list)
    seniority: str | None = None
    location: str | None = None
    work_model: str | None = None
    compensation: str | None = None
    explicit_signals: list[str] = field(default_factory=list)
    inferred_signals: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_text": self.source_text,
            "responsibilities": self.responsibilities,
            "must_have_requirements": self.must_have_requirements,
            "preferred_requirements": self.preferred_requirements,
            "skills": self.skills,
            "domain_terms": self.domain_terms,
            "seniority": self.seniority,
            "location": self.location,
            "work_model": self.work_model,
            "compensation": self.compensation,
            "explicit_signals": self.explicit_signals,
            "inferred_signals": self.inferred_signals,
            "ambiguities": self.ambiguities,
        }
