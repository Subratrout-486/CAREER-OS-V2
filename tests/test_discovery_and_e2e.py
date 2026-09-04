"""Tests for discovery, provider routing, end-to-end orchestration and dashboard.

Synthetic/local fixtures only - no real employer or provider is contacted.
"""

from __future__ import annotations

import asyncio

import pytest

from career_os.dashboard.service import DashboardService
from career_os.discovery.scraper import JobPageScraper
from career_os.discovery.service import DiscoveryItem, JobDiscoveryService
from career_os.execution.engine import Step
from career_os.execution.runner import ApplicationPlan
from career_os.execution.state import ExecutionStatus, ExecutionStore
from career_os.integrations.ats import RawATSJob
from career_os.models.evidence import EvidenceClaim, EvidenceKind, SupportStatus
from career_os.models.resume import ResumeBullet, ResumeProfile
from career_os.orchestration.e2e import EndToEndOrchestrator
from career_os.providers.routing import ModelRouter, OfflineAdapter


def _run(coro):
    return asyncio.run(coro)


def _raw_job(external_id="1", title="Support Engineer", company="Acme", url=None):
    return RawATSJob(
        provider="greenhouse",
        external_id=external_id,
        company=company,
        title=title,
        location="India",
        description="We need a Support Engineer with SQL and communication skills. 2+ years experience required.",
        job_url=url or f"https://boards.greenhouse.io/acme/jobs/{external_id}",
        posted_at=None,
        raw={},
    )


def _profile():
    return ResumeProfile(
        summary="Support engineer with SQL and customer-facing experience.",
        bullets=(
            ResumeBullet("Supported production SQL systems for 3 years.", ("exp-1",)),
            ResumeBullet("Resolved 200+ support tickets with high satisfaction.", ("exp-2",)),
        ),
    )


def _claims():
    return [
        EvidenceClaim(
            claim_id="exp-1",
            claim="Worked at Acme from 2021 to present as a support engineer, supporting production SQL systems.",
            kind=EvidenceKind.USER_PROVIDED,
            support=SupportStatus.SUPPORTED,
            confidence=0.9,
        ),
        EvidenceClaim(
            claim_id="exp-2",
            claim="Resolved over 200 support tickets involving SQL.",
            kind=EvidenceKind.USER_PROVIDED,
            support=SupportStatus.SUPPORTED,
            confidence=0.9,
        ),
    ]


def test_discovery_normalizes_and_ranks(tmp_path):
    svc = JobDiscoveryService()
    result = svc.ingest([DiscoveryItem("greenhouse", _raw_job(external_id="1"))])
    assert len(result.unique_jobs) == 1
    job = result.jobs[0]
    assert job.record.company == "Acme"
    assert job.record.title == "Support Engineer"
    assert job.record.source_type.value == "ATS"
    assert job.reliability == 1.0
    assert job.freshness == 0.5
    assert job.priority == pytest.approx(0.7)


def test_discovery_deduplicates(tmp_path):
    svc = JobDiscoveryService()
    result = svc.ingest(
        [
            DiscoveryItem("greenhouse", _raw_job(external_id="1")),
            DiscoveryItem("greenhouse", _raw_job(external_id="1")),
        ]
    )
    assert len(result.jobs) == 2
    unique = result.unique_jobs
    assert len(unique) == 1


def test_discovery_source_failure_isolated(tmp_path):
    svc = JobDiscoveryService()
    result = svc.ingest(
        [
            DiscoveryItem("broken", {"title": None, "company": None, "url": None}),  # invalid intake
            DiscoveryItem("greenhouse", _raw_job(external_id="9")),
        ]
    )
    # The good job still lands even though one source errored.
    assert len(result.unique_jobs) >= 1
    assert "broken" in result.source_errors


def test_scrapling_fixture():
    page = JobPageScraper(prefer="fixture").fetch("https://example.com/jobs/1")
    assert "Support Engineer" in page.title
    assert page.security_blocked is False


def test_provider_router_offline_always_available():
    router = ModelRouter()
    adapter = router.available("classification")
    assert adapter.provider == "offline"
    assert adapter.available() is True
    assert router.health()["offline"]["available"] is True


def test_offline_adapter_returns_empty():
    # Offline adapter completes without error and without inventing content.
    out = OfflineAdapter().complete(system="s", user="u")
    assert out == ""


def test_end_to_end_prepare_and_approve(tmp_path):
    store = ExecutionStore(tmp_path)
    orchestrator = EndToEndOrchestrator(
        store=store,
        resume=_profile(),
        claims=_claims(),
    )
    svc = JobDiscoveryService()
    discovered = svc.ingest([DiscoveryItem("greenhouse", _raw_job())])
    executions = orchestrator.prepare(discovered)
    assert len(executions) == 1
    assert executions[0].status == ExecutionStatus.READY_FOR_APPROVAL
    assert (executions[0].pipeline.get("fit") or {}).get("overall", 0) > 0


def test_end_to_end_approved_executes_and_verifies(tmp_path):
    store = ExecutionStore(tmp_path)
    orchestrator = EndToEndOrchestrator(store=store, resume=_profile(), claims=_claims())
    svc = JobDiscoveryService()
    discovered = svc.ingest([DiscoveryItem("greenhouse", _raw_job())])
    executions = orchestrator.prepare(discovered)

    def plan(execution):
        return ApplicationPlan(
            execution_id=execution.execution_id,
            url=execution.application_url,
            profile=execution.pipeline.get("profile", {}),
            fields=[],
            steps=[Step(kind="open", target=execution.application_url), Step(kind="verify", target=execution.application_url)],
            fixture_pages={
                "open": "<html><title>Apply</title><body>form</body></html>",
                "verify": "<html><title>Thanks</title><body>Your application has been submitted. Reference APP-42</body></html>",
            },
        )

    outcome = _run(orchestrator.run_approved(executions, plan_builder=plan))
    assert outcome.submitted == 1
    assert outcome.verified == 1
    assert store.by_job_key(executions[0].job_key)[0].status == ExecutionStatus.SUBMISSION_VERIFIED


def test_dashboard_metrics_from_state(tmp_path):
    store = ExecutionStore(tmp_path)
    orchestrator = EndToEndOrchestrator(store=store, resume=_profile(), claims=_claims())
    svc = JobDiscoveryService()
    discovered = svc.ingest([DiscoveryItem("greenhouse", _raw_job())])
    orchestrator.prepare(discovered)

    dash = DashboardService(store=store)
    snapshot = dash.snapshot()
    assert snapshot["totals"]["jobs_discovered"] == 1
    assert snapshot["totals"]["awaiting_approval"] == 1
    assert snapshot["pipeline_health"] == 100.0
    assert snapshot["latest_execution"]["status"] == ExecutionStatus.READY_FOR_APPROVAL
