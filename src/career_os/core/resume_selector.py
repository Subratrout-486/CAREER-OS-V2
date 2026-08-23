from __future__ import annotations

from dataclasses import dataclass

from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeProfile


@dataclass(frozen=True)
class ResumeCandidate:
    name: str
    profile: ResumeProfile
    focus_terms: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ResumeSelection:
    name: str
    score: float
    matched_terms: tuple[str, ...] = ()
    missing_terms: tuple[str, ...] = ()
    rationale: str = ""


def _norm(value: str) -> str:
    return " ".join(value.casefold().replace("/", " ").replace("-", " ").split())


class ResumeSelector:
    """Select the most relevant existing resume without inventing experience."""

    def select(self, jd: JDAnalysis, resumes: list[ResumeCandidate]) -> ResumeSelection:
        if not resumes:
            raise ValueError("At least one resume candidate is required")
        target = {_norm(x) for x in (jd.skills + jd.domain_terms + jd.responsibilities)}
        ranked: list[ResumeSelection] = []
        for resume in resumes:
            text = " ".join([resume.profile.summary, *(b.text for b in resume.profile.bullets)])
            corpus = _norm(text)
            focus = {_norm(x) for x in resume.focus_terms}
            matched = sorted(term for term in target | focus if term and term in corpus)
            missing = sorted(term for term in target if term and term not in corpus)
            score = 100.0 if not target else min(100.0, 100.0 * len(matched) / len(target))
            ranked.append(ResumeSelection(resume.name, round(score, 2), tuple(matched), tuple(missing[:20]), "Highest evidence overlap with the JD; no new claims were introduced."))
        return max(ranked, key=lambda item: (item.score, -len(item.missing_terms), item.name))
