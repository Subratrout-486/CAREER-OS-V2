from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from career_os.candidate_profile import load_candidate_source_of_truth
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceSource, SupportStatus
from career_os.models.resume import ResumeBullet, ResumeProfile
from career_os.pipeline import CareerPipeline, PipelineResult


@dataclass(frozen=True)
class JobProcessingRequest:
    """A job accepted by CareerOS is immediately eligible for processing."""

    job: Mapping[str, object]
    run_id: str | None = None


def _candidate_inputs(profile_path: Path) -> tuple[ResumeProfile, list[EvidenceClaim]]:
    profile = load_candidate_source_of_truth(profile_path)
    candidate = profile["candidate"]
    summary = str(candidate.get("professional_summary") or candidate.get("headline") or "").strip()

    bullets: list[ResumeBullet] = []
    claims: list[EvidenceClaim] = []
    for experience_index, experience in enumerate(profile["experience"]):
        group = f"exp-{experience_index}"
        responsibilities = experience.get("responsibilities", []) if isinstance(experience, dict) else []
        for responsibility_index, responsibility in enumerate(responsibilities):
            text = str(responsibility).strip()
            if not text:
                continue
            claim_id = f"{group}-{responsibility_index}"
            bullets.append(ResumeBullet(text=text, evidence_claim_ids=(claim_id,)))
            claims.append(
                EvidenceClaim(
                    claim_id=claim_id,
                    claim=text,
                    kind=EvidenceKind.USER_PROVIDED,
                    support=SupportStatus.SUPPORTED,
                    confidence=1.0,
                    source=EvidenceSource(
                        source_id=str(profile_path),
                        source_type="candidate_source_of_truth",
                        label="CareerOS candidate Source of Truth",
                    ),
                )
            )

    return ResumeProfile(summary=summary, bullets=tuple(bullets)), claims


def _run_id_for(job: Mapping[str, object]) -> str:
    canonical = json.dumps(
        {
            "company": job.get("company"),
            "title": job.get("title"),
            "location": job.get("location"),
            "url": job.get("url") or job.get("job_url") or job.get("source_url"),
            "description": job.get("description") or job.get("content"),
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


class AutomaticJobProcessor:
    """Turn every accepted job into a deterministic V2 processing run."""

    def __init__(self, *, candidate_path: Path | None = None, checkpoint_root: Path | None = None):
        self.candidate_path = candidate_path or Path("candidate/source_of_truth.json")
        self.checkpoint_root = checkpoint_root or Path(".career_os/automatic_runs")

    def process(self, request: JobProcessingRequest) -> PipelineResult:
        resume, claims = _candidate_inputs(self.candidate_path)
        run_id = request.run_id or _run_id_for(request.job)
        checkpoint = self.checkpoint_root / f"{run_id}.json"
        pipeline = CareerPipeline(checkpoint)
        return pipeline.run(
            run_id=run_id,
            raw_job=request.job,
            resume=resume,
            claims=claims,
        )
