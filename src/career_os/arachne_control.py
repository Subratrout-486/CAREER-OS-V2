"""ARACHNE live control plane.

This router is the single backend for the Career OS web application. Every
endpoint reads from real persisted/generated state - execution store, processed
job results, model provider health, and the candidate source of truth. There
are no hardcoded metrics.

The only state-changing actions are those a human performs through the UI:
approving a READY_FOR_APPROVAL application and withdrawing one. Approving never
auto-submits; it only authorizes the existing approval-gated execution engine.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from career_os.arachne_store import ArachneResultStore
from career_os.candidate_profile import load_candidate_source_of_truth
from career_os.dashboard.service import DashboardService
from career_os.execution.state import (
    ApplicationExecution,
    ApplicationExecutionStateMachine,
    ExecutionStatus,
    ExecutionStore,
    ExecutionTransitionError,
)
from career_os.orchestration.e2e import EndToEndOrchestrator
from career_os.providers.routing import ModelRouter

_EXECUTION_ORDER = [
    ExecutionStatus.READY_FOR_APPROVAL,
    ExecutionStatus.APPROVED,
    ExecutionStatus.QUEUED,
    ExecutionStatus.APPLYING,
    ExecutionStatus.SUBMITTED,
    ExecutionStatus.SUBMISSION_VERIFIED,
]


def _default_execution_root() -> Path:
    return Path(os.getenv("CAREER_OS_EXECUTION_ROOT", ".career_os/executions"))


def _default_arachne_root() -> Path:
    return Path(os.getenv("CAREER_OS_ARACHNE_ROOT", ".career_os/arachne"))


def _execution_payload(execution: ApplicationExecution) -> dict[str, Any]:
    """Serialize one application execution with all pipeline artifacts for the UI."""
    pipeline = execution.pipeline or {}
    return {
        "execution_id": execution.execution_id,
        "job_key": execution.job_key,
        "company": execution.company,
        "title": execution.title,
        "application_url": execution.application_url,
        "status": execution.status,
        "updated_at": execution.updated_at,
        "retry_count": execution.retry_count,
        "approval": execution.approval,
        "execution": execution.execution,
        "fit": pipeline.get("fit"),
        "jd": pipeline.get("jd"),
        "jd_quality": pipeline.get("jd_quality"),
        "evidence": pipeline.get("evidence", []),
        "ats_audit": pipeline.get("ats_audit"),
        "recruiter_review": pipeline.get("recruiter_review"),
        "profile": pipeline.get("profile"),
        "events": [
            {"status": ev.status, "occurred_at": ev.occurred_at, "detail": ev.detail}
            for ev in execution.events
        ],
    }


def create_arachne_control_router(
    *,
    execution_store: ExecutionStore | None = None,
    result_store: ArachneResultStore | None = None,
    dashboard: DashboardService | None = None,
    router: ModelRouter | None = None,
    candidate_path: Path | None = None,
    ats_discovery: Any | None = None,
) -> APIRouter:
    """Create the live ARACHNE control-plane router.

    Dependencies default to production state paths; tests can inject isolated
    stores so no project state is touched.

    ``ats_discovery`` is an ``ATSDiscoveryService`` used to scan a public careers
    URL through the registered ATS providers. It defaults to the real service
    which contacts live feeds only when ``/api/discover`` is called.
    """
    exec_store = execution_store or ExecutionStore(_default_execution_root())
    res_store = result_store or ArachneResultStore(_default_arachne_root())
    provider_router = router or ModelRouter()
    dashboard_service = dashboard or DashboardService(store=exec_store, router=provider_router)
    candidate = candidate_path or Path("candidate/source_of_truth.json")

    control = APIRouter(prefix="/api", tags=["arachne-control"])

    # ------------------------------------------------------------------ overview
    @control.get("/overview")
    def overview() -> dict[str, Any]:
        snapshot = dashboard_service.snapshot()
        executions = exec_store.list()
        queue = [e for e in executions if e.status == ExecutionStatus.READY_FOR_APPROVAL]
        return {
            "generated_at": snapshot["generated_at"],
            "totals": snapshot["totals"],
            "pipeline_health": snapshot["pipeline_health"],
            "provider_health": snapshot["provider_health"],
            "latest_execution": snapshot["latest_execution"],
            "recent_errors": snapshot["recent_errors"],
            "approval_queue_count": len(queue),
        }

    # ------------------------------------------------------------- job discovery
    @control.get("/jobs")
    def jobs() -> dict[str, Any]:
        executions = exec_store.list()
        return {
            "count": len(executions),
            "jobs": [
                _execution_payload(e)
                for e in sorted(executions, key=lambda x: x.updated_at, reverse=True)
            ],
        }

    @control.get("/jobs/{execution_id}")
    def job(execution_id: str) -> dict[str, Any]:
        execution = exec_store.load(execution_id)
        if execution is None:
            raise HTTPException(status_code=404, detail="job not found")
        return _execution_payload(execution)

    @control.get("/processed-jobs")
    def processed_jobs() -> dict[str, Any]:
        results = res_store.list()
        return {"count": len(results), "results": results}

    # ---------------------------------------------------------------- approval
    @control.get("/approval-queue")
    def approval_queue() -> dict[str, Any]:
        executions = [
            e for e in exec_store.list() if e.status == ExecutionStatus.READY_FOR_APPROVAL
        ]
        executions.sort(key=lambda e: (e.pipeline.get("fit") or {}).get("overall", 0), reverse=True)
        return {
            "count": len(executions),
            "items": [
                {
                    "execution_id": e.execution_id,
                    "company": e.company,
                    "title": e.title,
                    "application_url": e.application_url,
                    "fit_overall": (e.pipeline.get("fit") or {}).get("overall"),
                    "ats_score": (e.pipeline.get("ats_audit") or {}).get("score"),
                    "recommendation": (e.pipeline.get("recruiter_review") or {}).get(
                        "recommendation"
                    ),
                    "jd_quality": e.pipeline.get("jd_quality"),
                    "hard_gaps": (e.pipeline.get("fit") or {}).get("hard_gaps", []),
                }
                for e in executions
            ],
        }

    @control.post("/jobs/{execution_id}/approve")
    def approve(execution_id: str) -> dict[str, Any]:
        execution = exec_store.load(execution_id)
        if execution is None:
            raise HTTPException(status_code=404, detail="job not found")
        machine = ApplicationExecutionStateMachine(exec_store)
        try:
            machine.approve(execution)
        except ExecutionTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        exec_store.save(execution)
        return {"ok": True, "execution": _execution_payload(execution)}

    @control.post("/jobs/{execution_id}/withdraw")
    def withdraw(execution_id: str) -> dict[str, Any]:
        execution = exec_store.load(execution_id)
        if execution is None:
            raise HTTPException(status_code=404, detail="job not found")
        machine = ApplicationExecutionStateMachine(exec_store)
        machine.withdraw(execution)
        exec_store.save(execution)
        return {"ok": True, "execution": _execution_payload(execution)}

    # ------------------------------------------------------------- execution/history
    @control.get("/executions")
    def executions() -> dict[str, Any]:
        records = exec_store.list()
        order = {status: i for i, status in enumerate(_EXECUTION_ORDER)}
        return {
            "count": len(records),
            "executions": [
                {
                    "execution_id": e.execution_id,
                    "job_key": e.job_key,
                    "company": e.company,
                    "title": e.title,
                    "status": e.status,
                    "application_url": e.application_url,
                    "updated_at": e.updated_at,
                    "fit_overall": (e.pipeline.get("fit") or {}).get("overall"),
                    "stage_index": order.get(e.status, 99),
                }
                for e in records
            ],
        }

    @control.get("/executions/{execution_id}")
    def execution(execution_id: str) -> dict[str, Any]:
        execution = exec_store.load(execution_id)
        if execution is None:
            raise HTTPException(status_code=404, detail="execution not found")
        return _execution_payload(execution)

    @control.get("/history")
    def history() -> dict[str, Any]:
        executions = exec_store.list()
        all_events: list[dict[str, Any]] = []
        for e in executions:
            for ev in e.events:
                all_events.append(
                    {
                        "execution_id": e.execution_id,
                        "company": e.company,
                        "title": e.title,
                        "status": ev.status,
                        "occurred_at": ev.occurred_at,
                        "detail": ev.detail,
                    }
                )
        all_events.sort(key=lambda x: x.get("occurred_at", ""), reverse=True)
        return {"count": len(all_events), "events": all_events}

    # ---------------------------------------------------------------- providers
    @control.get("/providers")
    def providers() -> dict[str, Any]:
        return {"health": provider_router.health()}

    # ---------------------------------------------------------------- agent activity
    @control.get("/activity")
    def activity() -> dict[str, Any]:
        executions = exec_store.list()
        nodes: list[dict[str, Any]] = []
        for e in executions:
            nodes.extend(
                {
                    "execution_id": e.execution_id,
                    "company": e.company,
                    "title": e.title,
                    "stage": ev.status,
                    "occurred_at": ev.occurred_at,
                    "detail": ev.detail,
                }
                for ev in e.events
            )
        nodes.sort(key=lambda x: x.get("occurred_at", ""), reverse=True)
        return {"count": len(nodes), "nodes": nodes[:100]}

    # ---------------------------------------------------------------- candidate
    @control.get("/candidate")
    def candidate_view() -> dict[str, Any]:
        try:
            source = load_candidate_source_of_truth(candidate)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="candidate source of truth not found")
        return {"candidate": source}

    @control.get("/base-resume")
    def base_resume() -> dict[str, Any]:
        try:
            source = load_candidate_source_of_truth(candidate)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="candidate source of truth not found")
        cand = source.get("candidate", {}) or {}
        bullets: list[dict[str, Any]] = []
        for i, exp in enumerate(source.get("experience", [])):
            for j, responsibility in enumerate(exp.get("responsibilities", [])):
                if not str(responsibility).strip():
                    continue
                claim_id = f"exp-{i}-{j}"
                bullets.append(
                    {
                        "text": str(responsibility),
                        "evidence_claim_ids": [claim_id],
                        "section": str(exp.get("company", "")),
                        "dates": str(exp.get("dates", "")),
                        "claim_id": claim_id,
                    }
                )
        return {
            "summary": str(cand.get("professional_summary") or cand.get("headline") or ""),
            "bullets": bullets,
        }

    # ---------------------------------------------------------------- workflow demo / ingest
    @control.post("/discover-demo")
    def discover_demo() -> dict[str, Any]:
        """Run discovery against a verified local fixture and prepare executions.

        Deterministic and offline: uses the fixture discovery source only, then
        prepares ready-for-approval executions through the full analytic chain.
        """
        from career_os.discovery.service import DiscoveryItem, JobDiscoveryService
        from career_os.integrations.ats import RawATSJob

        resume, claims = _candidate_resume_and_claims(candidate)
        orchestrator = EndToEndOrchestrator(
            store=exec_store,
            resume=resume,
            claims=claims,
        )
        raw_job = RawATSJob(
            provider="greenhouse",
            external_id="demo-support-engineer",
            company="Acme",
            title="Support Engineer",
            location="India",
            description=(
                "We are hiring a Support Engineer to own production incidents. "
                "You will troubleshoot application failures, batch jobs, and data "
                "inconsistencies across Oracle databases and Linux servers. Strong SQL, "
                "Python automation, REST API validation, and root-cause analysis skills "
                "are required. Experience with ServiceNow and SLA monitoring is a plus."
            ),
            job_url="https://boards.greenhouse.io/acme/jobs/demo-support-engineer",
            posted_at=None,
            raw={},
        )
        discovered = JobDiscoveryService().ingest([DiscoveryItem("greenhouse", raw_job)])
        prepared = orchestrator.prepare(discovered)
        return {
            "prepared": len(prepared),
            "first_execution_id": prepared[0].execution_id if prepared else None,
        }

    # ---------------------------------------------------------------- real ATS discovery
    @control.post("/discover")
    def discover(payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Scan a public ATS careers URL and prepare ready-for-approval executions.

        Resolves the URL through the registered credential-free ATS providers
        (Greenhouse, Lever, Ashby, Workday, Rippling, SmartRecruiters, Teamtailor),
        normalizes/deduplicates the returned jobs, and pushes accepted jobs through
        the full analytic pipeline into READY_FOR_APPROVAL.

        Failures are never reported as success: an unrecognized careers URL or a
        provider unreachable at scan time is returned as an explicit blocked /
        degraded state with per-source errors.
        """
        from career_os.discovery.service import DiscoveryItem, JobDiscoveryService
        from career_os.integrations.ats_discovery import ATSDiscoveryService

        payload = payload or {}
        careers_url = str(payload.get("careers_url", "")).strip()
        if not careers_url:
            raise HTTPException(status_code=400, detail="careers_url is required")
        try:
            max_jobs = max(1, min(int(payload.get("max_jobs", 50) or 50), 200))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="max_jobs must be an integer") from exc

        scanner = ats_discovery or ATSDiscoveryService()
        result = scanner.scan(careers_url, max_jobs=max_jobs)

        if result.provider is None:
            return {
                "provider": None,
                "status": "unsupported",
                "blocked": True,
                "reason": "No supported ATS provider detected for the provided careers URL",
                "careers_url": careers_url,
                "jobs_scanned": 0,
                "unique_jobs": 0,
                "duplicates": 0,
                "source_errors": {},
                "prepared": 0,
                "execution_ids": [],
            }

        resume, claims = _candidate_resume_and_claims(candidate)
        orchestrator = EndToEndOrchestrator(
            store=exec_store,
            resume=resume,
            claims=claims,
        )
        items = [DiscoveryItem(result.provider, job) for job in result.jobs]
        discovered = JobDiscoveryService().ingest(items)
        prepared = orchestrator.prepare(discovered) if discovered.unique_jobs else []
        return {
            "provider": result.provider,
            "status": "ok" if prepared else "degraded",
            "blocked": not prepared,
            "reason": None
            if prepared
            else "ATS provider returned no acceptable jobs (rate-limited, empty, or all duplicates)",
            "careers_url": careers_url,
            "jobs_scanned": len(result.jobs),
            "unique_jobs": len(discovered.unique_jobs),
            "duplicates": len(discovered.jobs) - len(discovered.unique_jobs),
            "source_errors": discovered.source_errors,
            "prepared": len(prepared),
            "execution_ids": [e.execution_id for e in prepared],
        }

    # ---------------------------------------------------------------- interview / learning
    @control.get("/interview")
    def interview() -> dict[str, Any]:
        from career_os.agents.interview_coach import InterviewCoach
        from career_os.models.evidence import (
            EvidenceClaim,
            EvidenceKind,
            EvidenceLedger,
            EvidenceSource,
            SupportStatus,
        )
        from career_os.models.jd import JDAnalysis

        latest = _latest_execution(exec_store)
        if latest is None:
            return {"target_role": None, "questions": []}
        jd_data = latest.pipeline.get("jd") or {}
        jd = JDAnalysis(**jd_data) if jd_data else JDAnalysis(source_text="")
        claims = [
            EvidenceClaim(
                claim_id=c.get("claim_id"),
                claim=c.get("claim", ""),
                kind=EvidenceKind(c.get("kind", "user_provided")),
                support=SupportStatus(c.get("support", "supported")),
                confidence=float(c.get("confidence", 1.0)),
                source=(
                    EvidenceSource(
                        source_id=c["source"]["source_id"],
                        source_type=c["source"]["source_type"],
                        label=c["source"]["label"],
                    )
                    if c.get("source")
                    else None
                ),
            )
            for c in latest.pipeline.get("evidence", [])
        ]
        ledger = EvidenceLedger(tuple(claims))
        coach = InterviewCoach()
        questions = coach.prepare(jd, ledger)
        return {
            "target_role": latest.title,
            "questions": [
                {
                    "text": q.text,
                    "question_type": q.question_type.value
                    if hasattr(q.question_type, "value")
                    else str(q.question_type),
                    "competency": q.competency,
                    "difficulty": q.difficulty,
                    "follow_ups": list(q.follow_ups),
                    "evidence_basis": list(q.evidence_basis),
                }
                for q in questions
            ],
        }

    @control.get("/learning")
    def learning() -> dict[str, Any]:
        from career_os.agents.learning_agent import LearningAgent

        target = _latest_target_role(exec_store)
        gaps = _collect_gaps(exec_store)
        agent = LearningAgent()
        plan = agent.build_plan(target or "Target Role", gaps)
        return {
            "target_role": plan.target_role,
            "source_gaps": list(plan.source_gaps),
            "objectives": [
                {
                    "skill": o.skill,
                    "priority": o.priority.value
                    if hasattr(o.priority, "value")
                    else str(o.priority),
                    "rationale": o.rationale,
                    "prerequisites": list(o.prerequisites),
                    "resources": [r.model_dump() for r in o.resources],
                    "practice_tasks": [t.model_dump() for t in o.practice_tasks],
                    "readiness_checks": [rc.model_dump() for rc in o.readiness_checks],
                }
                for o in plan.objectives
            ],
        }

    # ---------------------------------------------------------------- web graph
    @control.get("/graph")
    def graph() -> dict[str, Any]:
        executions = exec_store.list()
        companies: dict[str, dict[str, Any]] = {}
        jobs: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for e in executions:
            job_node = {
                "id": e.execution_id,
                "kind": "job",
                "label": e.title,
                "company": e.company,
                "status": e.status,
                "fit": (e.pipeline.get("fit") or {}).get("overall"),
            }
            jobs.append(job_node)
            company_key = e.company or "unknown"
            if company_key not in companies:
                companies[company_key] = {
                    "id": f"company:{company_key}",
                    "kind": "company",
                    "label": company_key,
                    "jobs": 0,
                }
            companies[company_key]["jobs"] += 1
            edges.append(
                {
                    "source": job_node["id"],
                    "target": companies[company_key]["id"],
                    "kind": "company",
                }
            )
            edges.append(
                {"source": job_node["id"], "target": "candidate:core", "kind": "candidate"}
            )
            if e.status == ExecutionStatus.SUBMISSION_VERIFIED:
                edges.append(
                    {"source": job_node["id"], "target": "node:verified", "kind": "verified"}
                )

        nodes = [
            *jobs,
            *companies.values(),
            {"id": "candidate:core", "kind": "candidate", "label": "Candidate", "status": "active"},
            {"id": "node:verified", "kind": "outcome", "label": "Verified", "status": "verified"},
        ]
        return {"nodes": nodes, "edges": edges, "count": len(executions)}

    return control


def _candidate_resume_and_claims(candidate_path: Path):
    from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceSource, SupportStatus
    from career_os.models.resume import ResumeBullet, ResumeProfile

    source = load_candidate_source_of_truth(candidate_path)
    cand = source.get("candidate", {}) or {}
    summary = str(cand.get("professional_summary") or cand.get("headline") or "").strip()
    bullets: list[ResumeBullet] = []
    claims: list[EvidenceClaim] = []
    for i, exp in enumerate(source.get("experience", [])):
        for j, responsibility in enumerate(exp.get("responsibilities", [])):
            text = str(responsibility).strip()
            if not text:
                continue
            claim_id = f"exp-{i}-{j}"
            bullets.append(ResumeBullet(text=text, evidence_claim_ids=(claim_id,)))
            claims.append(
                EvidenceClaim(
                    claim_id=claim_id,
                    claim=text,
                    kind=EvidenceKind.USER_PROVIDED,
                    support=SupportStatus.SUPPORTED,
                    confidence=1.0,
                    source=EvidenceSource(
                        source_id=str(candidate_path),
                        source_type="candidate_source_of_truth",
                        label="CareerOS candidate Source of Truth",
                    ),
                )
            )
    return ResumeProfile(summary=summary, bullets=tuple(bullets)), claims


def _latest_target_role(exec_store: ExecutionStore) -> str | None:
    latest = _latest_execution(exec_store)
    return latest.title if latest else None


def _latest_execution(exec_store: ExecutionStore) -> ApplicationExecution | None:
    executions = exec_store.list()
    if not executions:
        return None
    return max(executions, key=lambda e: e.updated_at)


def _collect_gaps(exec_store: ExecutionStore) -> list[str]:
    gaps: list[str] = []
    for e in exec_store.list():
        fit = e.pipeline.get("fit") or {}
        gaps.extend(fit.get("hard_gaps", []))
        gaps.extend(fit.get("preferred_gaps", []))
    return list(dict.fromkeys(gaps))
