"""End-to-end autonomous job application orchestrator.

Composes discovery -> pipeline -> approval queue -> approved execution ->
verification -> tracking in one resumable, failure-isolated loop.

A single job's failure never aborts the batch. Applications are never executed
on an external site without explicit human approval. Security challenges are
classified as BLOCKED_SECURITY_CHALLENGE and never bypassed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

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
from career_os.models.resume import ResumeProfile


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

    def prepare(self, discovered: DiscoveryResult) -> list[ApplicationExecution]:
        """Turn discovered jobs into prepared executions at READY_FOR_APPROVAL.

        Deterministic only - no auth, no provider, no application action.
        """
        if self._store is None:
            raise RuntimeError("prepare requires an ExecutionStore")
        machine = ApplicationExecutionStateMachine(self._store)
        executions: list[ApplicationExecution] = []
        for job in discovered.unique_jobs:
            try:
                jd = self.jd_intelligence.analyze(job.record.description or "")
                ledger = self.evidence_analyzer.build_ledger(list(self.claims))
                fit = self.fit_scorer.score(jd, ledger)
                tailored = self.resume_tailor.tailor(self.resume, jd, ledger)
                ats = self.ats_auditor.audit(tailored, jd)
                review = self.recruiter_reviewer.review(jd, tailored, fit, ledger)
                execution = ApplicationExecution(
                    job_key=str(job.record.job_id),
                    company=job.record.company,
                    title=job.record.title,
                    application_url=str(job.record.source_url),
                    pipeline={
                        "profile": {
                            "summary": self.resume.summary,
                            "bullets": [
                                {"text": b.text, "evidence_claim_ids": list(b.evidence_claim_ids)}
                                for b in tailored.bullets
                            ],
                            "matched_keywords": list(tailored.matched_keywords),
                        },
                        "fields": [],
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
