from pathlib import Path

import pytest

from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceSource, SupportStatus
from career_os.models.resume import ResumeBullet, ResumeProfile
from career_os.pipeline import CareerPipeline


RAW_JOB = {
    "company": "Example Corp",
    "title": "Product Support Analyst",
    "location": "Hyderabad",
    "url": "https://example.com/jobs/123",
    "source": "official",
    "description": """Product Support Analyst
Location: Hyderabad
Responsibilities
- Troubleshoot customer issues using SQL and REST APIs.
Required Qualifications
- Experience with SQL.
Preferred Qualifications
- Experience with Tableau.
""",
}


def claims():
    return [
        EvidenceClaim(
            claim_id="c1",
            claim="Troubleshot customer issues using SQL",
            kind=EvidenceKind.USER_PROVIDED,
            support=SupportStatus.SUPPORTED,
            confidence=0.9,
        ),
        EvidenceClaim(
            claim_id="c2",
            claim="Built Tableau dashboards",
            kind=EvidenceKind.VERIFIED,
            support=SupportStatus.SUPPORTED,
            confidence=0.9,
            source=EvidenceSource("resume", "resume", "Candidate resume"),
        ),
    ]


def resume():
    return ResumeProfile(
        summary="Support professional",
        bullets=(
            ResumeBullet("Troubleshot customer issues using SQL", ("c1",)),
            ResumeBullet("Built Tableau dashboards", ("c2",)),
        ),
    )


def test_pipeline_completes_and_persists_all_stage_checkpoints(tmp_path: Path):
    pipeline = CareerPipeline(tmp_path / "checkpoint.json")
    result = pipeline.run(run_id="run-1", raw_job=RAW_JOB, resume=resume(), claims=claims())

    assert result.checkpoint.status == "completed"
    assert result.checkpoint.completed_stages == [
        "job_intake",
        "jd_intelligence",
        "evidence_analysis",
        "fit_scoring",
        "resume_tailoring",
        "ats_audit",
        "recruiter_review",
        "application_readiness",
    ]
    assert result.application_ready is False
    assert any("ATS:" in finding for finding in result.checkpoint.artifacts["application_readiness"]["findings"])

    restored = CareerPipeline(tmp_path / "checkpoint.json")
    assert restored.checkpoint is not None
    assert restored.checkpoint.status == "completed"
    assert restored.checkpoint.artifacts["application_readiness"]["ready"] is False


def test_pipeline_blocks_conflicting_evidence_before_fit(tmp_path: Path):
    conflicting = claims() + [
        EvidenceClaim(
            claim_id="c3",
            claim="Worked at Example Corp from 2020-2022",
            kind=EvidenceKind.USER_PROVIDED,
            support=SupportStatus.SUPPORTED,
            confidence=0.9,
        ),
        EvidenceClaim(
            claim_id="c4",
            claim="Worked at Example Corp from 2021-2024",
            kind=EvidenceKind.USER_PROVIDED,
            support=SupportStatus.SUPPORTED,
            confidence=0.9,
        ),
    ]
    pipeline = CareerPipeline(tmp_path / "checkpoint.json")
    with pytest.raises(RuntimeError, match="Evidence conflicts"):
        pipeline.run(run_id="run-2", raw_job=RAW_JOB, resume=resume(), claims=conflicting)
    assert pipeline.checkpoint is not None
    assert pipeline.checkpoint.status == "blocked"
    assert pipeline.checkpoint.completed_stages == ["job_intake", "jd_intelligence"]


def test_pipeline_blocks_missing_job_description(tmp_path: Path):
    raw = dict(RAW_JOB)
    raw.pop("description")
    pipeline = CareerPipeline(tmp_path / "checkpoint.json")
    with pytest.raises(RuntimeError, match="Job description is missing"):
        pipeline.run(run_id="run-3", raw_job=raw, resume=resume(), claims=claims())
    assert pipeline.checkpoint is not None
    assert pipeline.checkpoint.status == "blocked"
    assert pipeline.checkpoint.completed_stages == ["job_intake"]
