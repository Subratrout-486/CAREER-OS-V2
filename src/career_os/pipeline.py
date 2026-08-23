"""Deterministic end-to-end Career OS pipeline.

External providers may enrich inputs, but this pipeline never calls a provider,
merges pull requests, submits applications, or invents missing candidate facts.
Each stage writes a durable checkpoint so a failed run can resume safely.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

from career_os.agents.application_manager import ApplicationManager
from career_os.agents.ats_auditor import ATSAuditor
from career_os.agents.evidence_analyzer import EvidenceAnalyzer
from career_os.agents.fit_scorer import FitScorer
from career_os.agents.jd_intelligence import JDIntelligence
from career_os.agents.job_intake import JobIntakePipeline
from career_os.agents.recruiter_reviewer import RecruiterReviewer
from career_os.agents.resume_tailor import ResumeTailor
from career_os.models.evidence import EvidenceClaim, EvidenceLedger
from career_os.models.jd import JDAnalysis
from career_os.models.job import JobRecord
from career_os.models.resume import ResumeProfile, TailoredResume


STAGES = (
    "job_intake",
    "jd_intelligence",
    "evidence_analysis",
    "fit_scoring",
    "resume_tailoring",
    "ats_audit",
    "recruiter_review",
    "application_readiness",
)


@dataclass
class PipelineCheckpoint:
    run_id: str
    completed_stages: list[str] = field(default_factory=list)
    current_stage: str | None = None
    status: str = "ready"
    blocker: str | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineResult:
    checkpoint: PipelineCheckpoint
    job: JobRecord
    jd: JDAnalysis
    ledger: EvidenceLedger
    fit: Any
    tailored_resume: TailoredResume
    ats_audit: Any
    recruiter_review: Any
    application_ready: bool


class CareerPipeline:
    """Run the deterministic Career OS departments with durable stage boundaries."""

    def __init__(self, checkpoint_path: Path):
        self.checkpoint_path = checkpoint_path
        self.checkpoint = self._load()

    def run(
        self,
        *,
        run_id: str,
        raw_job: Mapping[str, object],
        resume: ResumeProfile,
        claims: Sequence[EvidenceClaim],
    ) -> PipelineResult:
        self._ensure_run(run_id)
        self.checkpoint.status = "running"

        job = JobIntakePipeline().normalize(raw_job)
        self._complete("job_intake", job.model_dump(mode="json"))

        if not job.description:
            raise self._blocked("Job description is missing; JD analysis cannot proceed without source text.")
        jd = JDIntelligence().analyze(job.description)
        self._complete("jd_intelligence", asdict(jd))

        ledger = EvidenceAnalyzer().build_ledger(list(claims))
        conflicts = EvidenceAnalyzer().conflicts(ledger)
        if conflicts:
            raise self._blocked("Evidence conflicts require review before fit or application readiness.")
        self._complete("evidence_analysis", ledger.to_dict())

        fit = FitScorer().score(jd, ledger)
        self._complete("fit_scoring", asdict(fit))

        tailored = ResumeTailor().tailor(resume, jd, ledger)
        self._complete("resume_tailoring", tailored.to_dict())

        audit = ATSAuditor().audit(resume, jd)
        self._complete("ats_audit", audit.to_dict())

        review = RecruiterReviewer().review(jd, tailored, fit, ledger)
        self._complete("recruiter_review", review.to_dict())

        application = ApplicationManager().create(job, resume_version=run_id)
        findings = []
        if fit.hard_gaps:
            findings.extend(f"Missing hard requirement: {gap}" for gap in fit.hard_gaps)
        if audit.findings:
            findings.extend(f"ATS: {finding.message}" for finding in audit.findings)
        if review.recommendation != "shortlist":
            findings.append(f"Recruiter recommendation: {review.recommendation}")
        ApplicationManager().mark_ready(application, findings)
        application_ready = ApplicationManager().is_submission_ready(application)
        self._complete(
            "application_readiness",
            {"application_id": str(application.application_id), "ready": application_ready, "findings": findings},
        )
        self.checkpoint.status = "completed"
        self._save()
        return PipelineResult(self.checkpoint, job, jd, ledger, fit, tailored, audit, review, application_ready)

    def _ensure_run(self, run_id: str) -> None:
        if self.checkpoint is None:
            self.checkpoint = PipelineCheckpoint(run_id=run_id)
        elif self.checkpoint.run_id != run_id:
            raise ValueError("checkpoint belongs to a different run")
        elif self.checkpoint.status == "completed":
            raise ValueError("run is already completed")

    def _complete(self, stage: str, artifact: Any) -> None:
        expected = STAGES[len(self.checkpoint.completed_stages)]
        if stage != expected:
            raise RuntimeError(f"stage order violation: expected {expected}, got {stage}")
        self.checkpoint.current_stage = stage
        self.checkpoint.artifacts[stage] = artifact
        self.checkpoint.completed_stages.append(stage)
        self.checkpoint.current_stage = None
        self._save()

    def _blocked(self, reason: str) -> RuntimeError:
        self.checkpoint.status = "blocked"
        self.checkpoint.blocker = reason
        self._save()
        return RuntimeError(reason)

    def _load(self) -> PipelineCheckpoint | None:
        if not self.checkpoint_path.exists():
            return None
        return PipelineCheckpoint(**json.loads(self.checkpoint_path.read_text()))

    def _save(self) -> None:
        if self.checkpoint is None:
            return
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(self.checkpoint), indent=2, sort_keys=True, default=str) + "\n"
        with tempfile.NamedTemporaryFile("w", dir=self.checkpoint_path.parent, delete=False) as handle:
            handle.write(payload)
            temporary = handle.name
        Path(temporary).replace(self.checkpoint_path)
