#!/usr/bin/env python3
"""Opt-in live end-to-end smoke: real ATS discovery into the full Career OS path.

Uses a real public ATS careers URL (network required). It validates that jobs
discovered from a live provider enter the existing ARACHNE control-plane
pipeline -> READY_FOR_APPROVAL -> human approve -> approved batch execution ->
SUBMISSION_VERIFIED with evidence -> restart persistence.

Execution uses the deterministic fixture driver inside an isolated temp store,
so no real employer is ever contacted even though real job listings are read.
Run only when you intend to hit public ATS feeds:

    PYTHONPATH=src python scripts/arachne_live_discovery_smoke.py [careers_url]
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def _submission_plan(execution):
    """Deterministic, offline-safe plan that still exercises the full engine.

    Replays synthetic HTML keyed to the real discovered job so the engine walks
    open -> fill -> click -> verify and records VERIFIED with evidence. No real
    employer is contacted: the fixture driver never issues a network request.
    """
    url = execution.application_url or "https://example.test/apply"
    from career_os.execution.engine import Step
    from career_os.execution.runner import ApplicationPlan

    return ApplicationPlan(
        execution_id=execution.execution_id,
        url=url,
        profile=execution.pipeline.get("profile", {}) or {},
        fields=execution.pipeline.get("fields", []) or [],
        steps=[
            Step(kind="open", target=url),
            Step(kind="fill", target="name"),
            Step(kind="click", target="submit"),
            Step(kind="wait"),
            Step(kind="verify", target=url),
        ],
        fixture_pages={
            "0": "<html><head><title>Apply</title></head><body><form><input name='name'></form></body></html>",
            "1": "<html><head><title>Thank you</title></head><body>Your application has been submitted successfully. Reference ATS-LIVE-001.</body></html>",
        },
    )


def _queue_and_execute(runner_cls, store, machine, executions, plan_builder):
    """Queue + execute already-approved executions (job was approved via HTTP)."""
    runner = runner_cls(
        store=store,
        machine=machine,
        plan_builder=plan_builder,
    )
    queued = runner.queue_batch(executions)
    outcome = asyncio.run(runner.execute_batch(queued))
    return queued, outcome


def main() -> int:
    careers_url = sys.argv[1] if len(sys.argv) > 1 else "https://boards.greenhouse.io/greenhouse"

    from career_os.execution.state import ExecutionStatus, ExecutionStore

    with tempfile.TemporaryDirectory() as tmp:
        store_root = Path(tmp) / "executions"
        store = ExecutionStore(store_root)

        from fastapi import FastAPI

        from career_os.arachne_control import create_arachne_control_router
        from career_os.execution.runner import ApplicationBatchRunner
        from career_os.execution.state import (
            ApplicationExecutionStateMachine,
        )

        app = FastAPI()
        app.include_router(create_arachne_control_router(execution_store=store))

        with TestClient(app) as client:
            # 1. Real ATS discovery -> existing pipeline.
            r = client.post("/api/discover", json={"careers_url": careers_url, "max_jobs": 5})
            assert r.status_code == 200, r.text
            body = r.json()
            provider = body.get("provider")
            prepared = body.get("prepared", 0)
            print(
                f"live discover {careers_url} -> provider={provider} "
                f"jobs_scanned={body.get('jobs_scanned')} unique={body.get('unique_jobs')} "
                f"prepared={prepared} status={body.get('status')} blocked={body.get('blocked')}"
            )
            if provider is None or prepared == 0:
                print(f"NOT BLOCKING: live board unavailable or empty ({body.get('reason')})")
                return 0

            # 2. Approval queue reflects real jobs.
            queue = client.get("/api/approval-queue")
            assert queue.status_code == 200
            ids = [item["execution_id"] for item in queue.json()["items"]]
            assert len(ids) == prepared, f"approval queue = {len(ids)} != prepared {prepared}"

            # 3. Human approve one -> APPROVED.
            exec_id = ids[0]
            apr = client.post(f"/api/jobs/{exec_id}/approve")
            assert apr.status_code == 200, apr.text
            assert apr.json()["execution"]["status"] == ExecutionStatus.APPROVED

            # 4. Drive the approved batch through the durable runner (fixture driver).
            machine = ApplicationExecutionStateMachine(store)
            executions = [store.load(exec_id)]
            assert executions[0] is not None
            _, outcome = _queue_and_execute(
                ApplicationBatchRunner,
                store,
                machine,
                executions,
                plan_builder=_submission_plan,
            )
            print(
                f"batch: queued={len(outcome.results)} verified={outcome.verified} "
                f"failed={outcome.failed} blocked={outcome.blocked_security}"
            )
            assert outcome.verified == 1, "approved execution did not reach VERIFIED"

            # 5. Verification evidence persisted.
            persisted = store.load(exec_id)
            assert persisted is not None
            assert persisted.status == ExecutionStatus.SUBMISSION_VERIFIED
            evidence = persisted.execution.get("verification_evidence", "")
            assert evidence, "no verification evidence persisted"
            assert "submission" in evidence.casefold(), evidence

            # 6. Restart persistence: fresh store reload keeps VERIFIED.
            store2 = ExecutionStore(store_root)
            reloaded = store2.load(exec_id)
            assert reloaded is not None
            assert reloaded.status == ExecutionStatus.SUBMISSION_VERIFIED

    print(f"LIVE DISCOVERY E2E OK: provider={provider} first_job={exec_id}")
    print("real ATS discovery -> pipeline -> approval -> verified: verified")
    print("verification evidence + restart persistence: verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
