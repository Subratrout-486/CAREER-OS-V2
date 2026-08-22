from __future__ import annotations

import re

from career_os.models.evidence import EvidenceLedger, SupportStatus
from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeBullet, ResumeProfile, TailoredResume

_STOPWORDS = {
    "and", "the", "with", "for", "from", "that", "this", "have", "has", "years",
    "year", "using", "use", "ability", "strong", "good", "work", "working", "role",
}


def _terms(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9+#.-]+", text.casefold())
        if len(token) > 2 and token not in _STOPWORDS
    }


class ResumeTailor:
    """Creates a conservative JD-aligned resume draft from existing facts."""

    name = "resume_tailor"

    def tailor(self, resume: ResumeProfile, jd: JDAnalysis, ledger: EvidenceLedger) -> TailoredResume:
        supported_claims = {
            claim.claim_id: claim
            for claim in ledger.claims
            if claim.support in {SupportStatus.SUPPORTED, SupportStatus.PARTIALLY_SUPPORTED}
        }
        jd_terms = _terms(" ".join((*jd.must_have_requirements, *jd.preferred_requirements, *jd.skills)))

        ranked: list[tuple[int, ResumeBullet]] = []
        for bullet in resume.bullets:
            terms = _terms(bullet.text)
            overlap = len(terms.intersection(jd_terms))
            valid_ids = tuple(cid for cid in bullet.evidence_claim_ids if cid in supported_claims)
            if valid_ids:
                ranked.append((overlap, ResumeBullet(bullet.text, valid_ids)))

        ranked.sort(key=lambda item: item[0], reverse=True)
        selected = tuple(bullet for _, bullet in ranked)
        matched = tuple(sorted({term for bullet in selected for term in _terms(bullet.text).intersection(jd_terms)}))
        used_ids = {cid for bullet in selected for cid in bullet.evidence_claim_ids}
        omitted = tuple(sorted(set(supported_claims) - used_ids))

        summary = resume.summary.strip()
        edit_trace = ("Reordered evidence-backed bullets by JD relevance.",)
        if matched:
            edit_trace += ("Prioritized existing JD-aligned keywords without adding new claims.",)

        return TailoredResume(
            summary=summary,
            bullets=selected,
            matched_keywords=matched,
            omitted_claim_ids=omitted,
            edit_trace=edit_trace,
        )
