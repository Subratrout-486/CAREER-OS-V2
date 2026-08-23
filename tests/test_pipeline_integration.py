from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from career_os.models.evidence import (
    EvidenceClaim,
    EvidenceKind,
    EvidenceSource,
    SupportStatus,
)
from career_os.models.resume import ResumeBullet, ResumeProfile
from career_os.pipeline import CareerPipeline, STAGES


def test_pipeline_completes_all_deterministic_stages() -> None:
    job_url = "https://example.com/jobs/data-analyst-1"
    raw_job = {
        "company": "Example Co",
        "title": "Data Analyst",
        "location": "Hyderabad",
        "source_url": job_url,
        "source": "example",
        "description": (
            "Responsibilities\n"
            "Analyze data and support reporting.\n"
            "Requirements\n"
            "SQL\n"
            "Excel\n"
            "Preferred Qualifications\n"
            "Power BI"
        ),
    }
    claims = [
        EvidenceClaim(
            claim_id="sql",
            claim="Uses SQL for analysis",
            kind=EvidenceKind.VERIFIED,
            support=SupportStatus.SUPPORTED,
            confidence=0.95,
            source=EvidenceSource("resume-1", "resume", "verified resume"),
        ),
        EvidenceClaim(
            claim_id="excel",
            claim="Uses Excel for reporting",
            kind=EvidenceKind.USER_PROVIDED,
            support=SupportStatus.SUPPORTED,
            confidence=0.9,
        ),
    ]
    resume = ResumeProfile(
        summary="Analyst experienced in data and reporting.",
        bullets=(
            ResumeBullet("Used SQL for analysis and reporting.", ("sql",)),
            ResumeBullet("Used Excel for reporting workflows.", ("excel",)),
        ),
    )

    with TemporaryDirectory() as directory:
        result = CareerPipeline(Path(directory) / "checkpoint.json").run(
            run_id=str(uuid4()),
            raw_job=raw_job,
            resume=resume,
            claims=claims,
        )

    assert result.checkpoint.status == "completed"
    assert result.checkpoint.completed_stages == list(STAGES)
    assert result.job.company == "Example Co"
    assert result.jd.skills == ["sql", "power bi", "excel"]
    assert result.application_ready is False
    assert result.checkpoint.blocker is None


def test_pipeline_blocks_missing_job_description() -> None:
    raw_job = {
        "company": "Example Co",
        "title": "Data Analyst",
        "source_url": "https://example.com/jobs/data-analyst-2",
        "source": "example",
    }
    resume = ResumeProfile(summary="Analyst", bullets=())

    with TemporaryDirectory() as directory:
        pipeline = CareerPipeline(Path(directory) / "checkpoint.json")
        try:
            pipeline.run(run_id="missing-jd", raw_job=raw_job, resume=resume, claims=[])
        except RuntimeError as exc:
            assert "Job description is missing" in str(exc)
        else:
            raise AssertionError("Expected missing JD to block the pipeline")

        assert pipeline.checkpoint is not None
        assert pipeline.checkpoint.status == "blocked"
        assert pipeline.checkpoint.completed_stages == ["job_intake"]
        assert pipeline.checkpoint.blocker is not None
