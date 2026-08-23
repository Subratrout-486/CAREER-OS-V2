from __future__ import annotations

from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeBullet, ResumeProfile, TailoredResume


def _norm(value: str) -> str:
    return " ".join(value.casefold().replace("/", " ").replace("-", " ").split())


def _contains(term: str, text: str) -> bool:
    t = _norm(term)
    c = _norm(text)
    return bool(t) and t in c


class ResumeTailor:
    """Reorder and lightly tailor existing evidence-backed resume content.

    This layer deliberately does not invent achievements, metrics, employers,
    tools, or responsibilities. It can prioritize existing bullets and expose
    JD terms already supported by the source resume.
    """

    def tailor(self, jd: JDAnalysis, resume: ResumeProfile) -> TailoredResume:
        corpus = " ".join([resume.summary, *(b.text for b in resume.bullets)])
        target_terms = list(dict.fromkeys(jd.skills + jd.domain_terms + jd.responsibilities))
        matched = tuple(term for term in target_terms if _contains(term, corpus))

        def rank(bullet: ResumeBullet) -> tuple[int, int]:
            hits = sum(1 for term in target_terms if _contains(term, bullet.text))
            return hits, -len(bullet.text)

        ordered = tuple(sorted(resume.bullets, key=rank, reverse=True))
        trace = (
            "Prioritized existing bullets by JD evidence overlap.",
            "Preserved source wording unless already supported by the resume.",
            "Did not introduce unsupported claims or metrics.",
        )
        return TailoredResume(
            summary=resume.summary,
            bullets=ordered,
            matched_keywords=matched,
            omitted_claim_ids=(),
            edit_trace=trace,
        )
