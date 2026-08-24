from __future__ import annotations

from pathlib import Path

from career_os.candidate_profile import DEFAULT_SOURCE_OF_TRUTH, load_candidate_source_of_truth
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceLedger, EvidenceSource, SupportStatus
from career_os.models.resume import ResumeBullet, ResumeProfile


def load_canonical_candidate(path: Path = DEFAULT_SOURCE_OF_TRUTH) -> tuple[ResumeProfile, EvidenceLedger]:
    profile = load_candidate_source_of_truth(path)
    candidate = profile["candidate"]
    source = EvidenceSource(str(path), "canonical_candidate_source_of_truth", "CAREER-OS-V2 candidate/source_of_truth.json")
    claims = []
    bullets = []
    for experience in profile["experience"]:
        employer = str(experience["company"])
        role = str(experience["title"])
        dates = str(experience["dates"])
        for index, responsibility in enumerate(experience["responsibilities"]):
            claim_id = f"experience:{employer}:{index}"
            claims.append(EvidenceClaim(
                claim_id=claim_id,
                claim=f"{employer} — {role} ({dates}): {responsibility}",
                kind=EvidenceKind.VERIFIED,
                support=SupportStatus.SUPPORTED,
                confidence=1.0,
                source=source,
                notes="Loaded from canonical candidate Source of Truth.",
            ))
            bullets.append(ResumeBullet(str(responsibility), (claim_id,)))
    for index, skill in enumerate(profile["skills_and_tools"]["professional_experience"]):
        claims.append(EvidenceClaim(
            claim_id=f"professional-skill:{index}:{skill}",
            claim=f"Professional experience with {skill}",
            kind=EvidenceKind.VERIFIED,
            support=SupportStatus.SUPPORTED,
            confidence=1.0,
            source=source,
            notes="Loaded from canonical candidate Source of Truth.",
        ))
    return ResumeProfile(str(candidate["professional_summary"]), tuple(bullets)), EvidenceLedger(tuple(claims))
