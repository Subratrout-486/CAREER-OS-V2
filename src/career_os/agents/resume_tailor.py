from __future__ import annotations

import re

from career_os.models.evidence import EvidenceLedger, SupportStatus
from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeBullet, ResumeProfile, TailoredResume

_STOPWORDS = {
    "and", "the", "with", "for", "from", "that", "this", "have", "has", "years",
    "year", "using", "use", "ability", "strong", "good", "work", "working", "role",
}

_ALIASES = {
    "powerbi": "power bi",
    "power-bi": "power bi",
    "restful api": "rest api",
    "restful apis": "rest api",
    "postgres": "postgresql",
    "postgres db": "postgresql",
    "amazon web services": "aws",
    "microsoft azure": "azure",
    "google cloud platform": "gcp",
}

# Candidate-facing resumes are one-page artifacts. Keep the evidence ledger
# complete, but select only the strongest evidence-backed bullets for output.
_MAX_TAILORED_BULLETS = 18


def _canonical_text(text: str) -> str:
    value = text.casefold()
    for alias, canonical in sorted(_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        value = re.sub(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", canonical, value)
    return value


def _terms(text: str) -> set[str]:
    canonical = _canonical_text(text)
    tokens = {
        token for token in re.findall(r"[a-z0-9+#.-]+", canonical)
        if len(token) > 2 and token not in _STOPWORDS
    }
    phrases = {
        canonical_phrase
        for canonical_phrase in _ALIASES.values()
        if " " in canonical_phrase and re.search(
            rf"(?<![a-z0-9]){re.escape(canonical_phrase)}(?![a-z0-9])", canonical
        )
    }
    return tokens | phrases


def _experience_group(claim_id: str) -> str | None:
    if not claim_id.startswith("exp-"):
        return None
    prefix, _, _ = claim_id.rpartition("-")
    return prefix


class ResumeTailor:
    """Create a conservative JD-aligned resume from existing candidate facts."""

    name = "resume_tailor"

    def tailor(self, resume: ResumeProfile, jd: JDAnalysis, ledger: EvidenceLedger) -> TailoredResume:
        supported_claims = {
            claim.claim_id: claim
            for claim in ledger.claims
            if claim.support in {SupportStatus.SUPPORTED, SupportStatus.PARTIALLY_SUPPORTED}
        }

        hard_terms = _terms(" ".join(jd.must_have_requirements))
        preferred_terms = _terms(" ".join(jd.preferred_requirements))
        skill_terms = _terms(" ".join(jd.skills))
        jd_terms = hard_terms | preferred_terms | skill_terms

        ranked: list[tuple[tuple[int, int, int, int, int], ResumeBullet]] = []
        for position, bullet in enumerate(resume.bullets):
            valid_ids = tuple(cid for cid in bullet.evidence_claim_ids if cid in supported_claims)
            if not valid_ids:
                continue
            terms = _terms(bullet.text)
            relevance = (
                len(terms.intersection(hard_terms)),
                len(terms.intersection(preferred_terms)),
                len(terms.intersection(skill_terms)),
                len(terms.intersection(jd_terms)),
                -position,
            )
            ranked.append((relevance, ResumeBullet(bullet.text, valid_ids)))

        ranked.sort(key=lambda item: item[0], reverse=True)

        # Reserve one bullet for each professional experience group so a role
        # is not silently erased when another role has stronger keyword overlap.
        selected: list[ResumeBullet] = []
        selected_ids: set[str] = set()
        groups_seen: set[str] = set()
        for _, bullet in ranked:
            group = _experience_group(bullet.evidence_claim_ids[0]) if bullet.evidence_claim_ids else None
            if group and group not in groups_seen and len(selected) < _MAX_TAILORED_BULLETS:
                selected.append(bullet)
                selected_ids.update(bullet.evidence_claim_ids)
                groups_seen.add(group)

        for _, bullet in ranked:
            if len(selected) >= _MAX_TAILORED_BULLETS:
                break
            if any(cid in selected_ids for cid in bullet.evidence_claim_ids):
                continue
            selected.append(bullet)
            selected_ids.update(bullet.evidence_claim_ids)

        selected_tuple = tuple(selected)
        matched = tuple(sorted({term for bullet in selected_tuple for term in _terms(bullet.text).intersection(jd_terms)}))
        omitted = tuple(sorted(set(supported_claims) - selected_ids))

        trace = (
            "Reordered evidence-backed bullets by JD relevance.",
            f"Selected at most {_MAX_TAILORED_BULLETS} evidence-backed bullets for the candidate-facing one-page artifact.",
            "Omitted claims remain traceable in omitted_claim_ids and are not deleted from the evidence ledger.",
        )
        if matched:
            trace += ("Prioritized existing JD-aligned keywords without adding new claims.",)
        if hard_terms:
            trace += ("Weighted explicit must-have requirements above preferred requirements and general skills.",)

        return TailoredResume(
            summary=resume.summary.strip(),
            bullets=selected_tuple,
            matched_keywords=matched,
            omitted_claim_ids=omitted,
            edit_trace=trace,
        )
