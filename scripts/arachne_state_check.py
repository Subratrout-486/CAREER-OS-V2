"""Verify ARACHNE's control-plane data layer reads REAL persisted state.

Seeds the execution store through the real EndToEndOrchestrator (so the job
goes through ingest -> JD -> fit -> tailoring -> ATS -> READY_FOR_APPROVAL),
then verifies the DashboardService snapshot (the same data ARACHNE serves)
reflects that state. No fake data, no real employers.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from career_os.discovery.service import DiscoveryItem, JobDiscoveryService
from career_os.execution.state import ExecutionStatus
from career_os.orchestration.e2e import EndToEndOrchestrator
from career_os.dashboard.service import DashboardService

REPO = Path(__file__).resolve().parent.parent


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="arachne-state-"))
    os.environ["CAREER_OS_EXECUTION_ROOT"] = str(root / "executions")
    os.environ["CAREER_OS_ARACHNE_ROOT"] = str(root / "arachne")

    from career_os.integrations.ats import RawATSJob
    from career_os.models.evidence import EvidenceClaim, EvidenceKind, SupportStatus
    from career_os.models.resume import ResumeBullet, ResumeProfile

    resume = ResumeProfile(
        summary="Support engineer with Linux, AWS and Python automation experience.",
        bullets=(
            ResumeBullet("Supported production Linux systems for 3 years.", ("exp-1",)),
            ResumeBullet("Automated incident response with Python and AWS.", ("exp-2",)),
        ),
    )
    claims = [
        EvidenceClaim(
            claim_id="exp-1",
            claim="Worked as a support engineer maintaining Linux production systems.",
            kind=EvidenceKind.USER_PROVIDED,
            support=SupportStatus.SUPPORTED,
            confidence=0.9,
        ),
        EvidenceClaim(
            claim_id="exp-2",
            claim="Built Python automation for incident response on AWS.",
            kind=EvidenceKind.USER_PROVIDED,
            support=SupportStatus.SUPPORTED,
            confidence=0.9,
        ),
    ]

    svc = JobDiscoveryService()
    raw = RawATSJob(
        provider="fixture",
        external_id="gh-9001",
        title="Support Engineer",
        company="Acme Fixtures",
        location="India",
        description=(
            "Acme Fixtures seeks a Support Engineer with Linux troubleshooting, "
            "AWS, Python automation, and incident management experience."
        ),
        job_url="https://fixture.invalid/apply",
        posted_at=None,
        raw={},
    )
    discovered = svc.ingest([DiscoveryItem("fixture", raw)])
    store = __import__("career_os.execution.state", fromlist=["ExecutionStore"]).ExecutionStore(
        root / "executions"
    )
    orch = EndToEndOrchestrator(store=store, resume=resume, claims=claims)
    executions = orch.prepare(discovered)
    assert len(executions) == 1
    assert executions[0].status == ExecutionStatus.READY_FOR_APPROVAL
    exec_id = executions[0].execution_id
    print(f"seeded execution    : {exec_id} status={executions[0].status}")

    dash = DashboardService(store=store)
    snapshot = dash.snapshot()
    totals = snapshot["totals"]
    print(f"projects_discovered : {totals.get('jobs_discovered')}")
    print(f"awaiting_approval   : {totals.get('awaiting_approval')}")
    print(f"pipeline_health     : {snapshot.get('pipeline_health')}")
    assert totals.get("jobs_discovered") == 1
    assert totals.get("awaiting_approval") == 1
    assert snapshot.get("pipeline_health") == 100.0
    assert snapshot["latest_execution"]["status"] == ExecutionStatus.READY_FOR_APPROVAL
    by_status = snapshot["by_status"]
    print(f"by_status           : READY_FOR_APPROVAL={by_status.get('READY_FOR_APPROVAL')}")
    assert by_status.get("READY_FOR_APPROVAL") == 1
    assert snapshot["latest_execution"]["company"] == "Acme Fixtures"
    assert snapshot["latest_execution"]["title"] == "Support Engineer"
    print("ARACHNE STATE CHECK : OK  (control plane reads real persisted state)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())