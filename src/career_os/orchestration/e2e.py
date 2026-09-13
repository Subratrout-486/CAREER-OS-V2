"""End-to-end autonomous job application orchestrator.

Composes discovery -> pipeline -> approval queue -> approved execution ->
verification -> tracking in one resumable, failure-isolated loop.

A single job's failure never aborts the batch. Applications are never executed
on an external site without explicit human approval. Security challenges are
classified as BLOCKED_SECURITY_CHALLENGE and never bypassed.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from career_os.agents.application_manager import ApplicationManager
from career_os.agents.ats_auditor import ATSAuditor
from career_os.agents.evidence_analyzer import EvidenceAnalyzer
from career_os.agents.fit_scorer import FitScorer
from career_os.agents.jd_intelligence import JDIntelligence
from career_os.agents.recruiter_reviewer import RecruiterReviewer
from career_os.agents.resume_tailor import ResumeTailor
from career_os.autoapply.adapter import build_application_plan
from career_os.discovery.service import DiscoveryResult, JobDiscoveryService
from career_os.execution.engine import ApplicationExecutor
from career_os.execution.runner import ApplicationBatchRunner, ApplicationPlan, BatchOutcome
from career_os.execution.state import (
    ApplicationExecution,
    ApplicationExecutionStateMachine,
    ExecutionStore,
)
from career_os.models.evidence import EvidenceClaim
from career_os.models.resume import ResumeProfile, TailoredResume


@dataclass
class EndToEndResult:
    discovered: int = 0
    ready_for_approval: int = 0
    approved: int = 0
    queued: int = 0
    submitted: int = 0
    verified: int = 0
    blocked_security: int = 0
    failed: int = 0
    batch: BatchOutcome | None = None
    errors: dict[str, str] = field(default_factory=dict)


class EndToEndOrchestrator:
    """Drive the complete loop using the existing pipeline and execution engine."""

    def __init__(
        self,
        *,
        discovery: JobDiscoveryService | None = None,
        store: ExecutionStore | None = None,
        resume: ResumeProfile | None = None,
        claims: list[EvidenceClaim] | None = None,
        plan_builder: Callable[[ApplicationExecution], ApplicationPlan] | None = None,
        jd_intelligence: JDIntelligence | None = None,
        evidence_analyzer: EvidenceAnalyzer | None = None,
        fit_scorer: FitScorer | None = None,
        resume_tailor: ResumeTailor | None = None,
        ats_auditor: ATSAuditor | None = None,
        recruiter_reviewer: RecruiterReviewer | None = None,
        application_manager: ApplicationManager | None = None,
    ) -> None:
        self.discovery = discovery or JobDiscoveryService()
        self.resume = resume or ResumeProfile(summary="")
        self.claims = claims or []
        self.jd_intelligence = jd_intelligence or JDIntelligence()
        self.evidence_analyzer = evidence_analyzer or EvidenceAnalyzer()
        self.fit_scorer = fit_scorer or FitScorer()
        self.resume_tailor = resume_tailor or ResumeTailor()
        self.ats_auditor = ats_auditor or ATSAuditor()
        self.recruiter_reviewer = recruiter_reviewer or RecruiterReviewer()
        self.application_manager = application_manager or ApplicationManager()
        self.plan_builder = plan_builder
        self._store = store

    def _candidate_source(self):  # noqa: ANN201 - light loader used only for resume artifact naming
        from career_os.candidate_profile import load_candidate_source_of_truth

        return load_candidate_source_of_truth(
            Path(os.getenv("CAREER_OS_CANDIDATE_PATH", "candidate/source_of_truth.json"))
        )

    def _persist_resume_pdf(self, *, profile: dict[str, object], tailored: TailoredResume, target_role: str) -> str | None:
        """Render the tailored resume to a validated PDF artifact for upload.

        Renders to ``.career-os/resumes/Subrat_Rout_[Target_Role].pdf`` and
        validates it before returning the path. Returns ``None`` (never a fake
        path) when rendering/validation fails so the application can proceed
        without a fabricated resume.
        """
        try:
            from career_os.resume_artifact import (
                render_resume_html,
                render_resume_pdf,
                resume_filename,
                validate_resume_pdf,
            )
        except Exception:  # noqa: BLE001 - optional rendering must not abort the loop
            return None

        try:
            source = self._candidate_source()
            candidate = source.get("candidate", {}) or {}
            name = str(candidate.get("name", "")).strip()
            filename = resume_filename(name, target_role)
            root = Path(os.getenv("CAREER_OS_RESUME_ROOT", ".career-os/resumes"))
            root.mkdir(parents=True, exist_ok=True)
            html_path = root / filename.replace(".pdf", ".html")
            pdf_path = root / filename
            html_path.write_text(
                render_resume_html(profile, tailored, target_role=target_role),
                encoding="utf-8",
            )
            render_resume_pdf(html_path.read_text(encoding="utf-8"), pdf_path)
            if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
                return None
            validate_resume_pdf(pdf_path, name)
            return str(pdf_path)
        except Exception:  # noqa: BLE001 - a failed resume render never blocks discovery
            return None

    def prepare(self, discovered: DiscoveryResult) -> list[ApplicationExecution]:
        """Turn discovered jobs into prepared executions at READY_FOR_APPROVAL.

        Deterministic only - no auth, no provider, no application action.
        """
        if self._store is None:
            raise RuntimeError("prepare requires an ExecutionStore")
        machine = ApplicationExecutionStateMachine(self._store)
        executions: list[ApplicationExecution] = []
        candidate_profile = self._candidate_source()
        profile_map = {
            "summary": self.resume.summary,
            "bullets": [
                {"text": b.text, "evidence_claim_ids": list(b.evidence_claim_ids)}
                for b in self.resume.bullets
            ],
        }
        candidate_info = candidate_profile.get("candidate", {}) or {}
        if isinstance(candidate_info, dict):
            # Verified flat candidate fields, derived from the Source of Truth
            # only. Full name is split into first/last deterministically so the
            # form mapper can answer first/last-name controls.
            name = str(candidate_info.get("name", "")).strip()
            if name:
                profile_map["full_name"] = name
                parts = name.split(" ", 1)
                profile_map["first_name"] = parts[0]
                if len(parts) > 1:
                    profile_map["last_name"] = parts[1]
            for key in ("email", "phone", "linkedin_url", "portfolio_url", "location", "headline", "work_authorization", "sponsorship"):
                if candidate_info.get(key):
                    profile_map[key] = candidate_info[key]
        for job in discovered.unique_jobs:
            try:
                jd = self.jd_intelligence.analyze(job.record.description or "")
                ledger = self.evidence_analyzer.build_ledger(list(self.claims))
                fit = self.fit_scorer.score(jd, ledger)
                tailored = self.resume_tailor.tailor(self.resume, jd, ledger)
                ats = self.ats_auditor.audit(tailored, jd)
                review = self.recruiter_reviewer.review(jd, tailored, fit, ledger)
                resume_path = self._persist_resume_pdf(
                    profile=candidate_profile,
                    tailored=tailored,
                    target_role=job.record.title or "Target_Role",
                )
                execution = ApplicationExecution(
                    job_key=str(job.record.job_id),
                    company=job.record.company,
                    title=job.record.title,
                    application_url=str(job.record.source_url),
                    pipeline={
                        "profile": profile_map,
                        "fields": [],
                        "resume_path": resume_path,
                        "target_role": job.record.title or "",
                        "fit": fit.to_dict(),
                        "jd": jd.to_dict(),
                        "evidence": [
                            {
                                "claim_id": c.claim_id,
                                "claim": c.claim,
                                "kind": c.kind.value,
                                "support": c.support.value,
                                "confidence": c.confidence,
                                "source": {
                                    "source_id": c.source.source_id,
                                    "source_type": c.source.source_type,
                                    "label": c.source.label,
                                }
                                if c.source
                                else None,
                            }
                            for c in ledger.claims
                        ],
                        "ats_audit": ats.to_dict(),
                        "recruiter_review": review.to_dict(),
                        "jd_quality": jd.analysis_quality,
                    },
                )
                machine.advance_to_ready(execution)
                self._store.save(execution)
                executions.append(execution)
            except Exception:  # noqa: BLE001, S112 - one bad job must not abort the batch
                continue
        return executions

    async def run_approved(
        self,
        executions: list[ApplicationExecution],
        *,
        plan_builder: Callable[[ApplicationExecution], ApplicationPlan] | None = None,
    ) -> BatchOutcome:
        """Approve, queue and autonomously execute a batch."""
        if self._store is None:
            raise RuntimeError("run_approved requires an ExecutionStore")
        machine = ApplicationExecutionStateMachine(self._store)
        runner = ApplicationBatchRunner(
            self._store,
            machine,
            executor=ApplicationExecutor(),
            plan_builder=plan_builder or self.plan_builder or _default_plan,
        )
        approved = runner.approve_batch(executions)
        queued = runner.queue_batch(approved)
        return await runner.execute_batch(queued)


def _default_plan(execution: ApplicationExecution) -> ApplicationPlan:
    return build_application_plan(execution)
