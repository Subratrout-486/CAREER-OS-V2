"""Tests for durable restart/resume, idempotency, isolated failure and APIs.

Synthetic/local fixtures only.
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from career_os.execution.engine import Step
from career_os.execution.runner import ApplicationBatchRunner, ApplicationPlan
from career_os.execution.state import (
    ApplicationExecution,
    ApplicationExecutionStateMachine,
    ExecutionStatus,
    ExecutionStore,
)
from career_os.state_api import create_state_router


def _run(coro):
    return asyncio.run(coro)


def _fixture_plan_submit(execution, pages=None):
    return ApplicationPlan(
        execution_id=execution.execution_id,
        url=execution.application_url,
        profile=execution.pipeline.get("profile", {}),
        fields=[],
        steps=[Step(kind="open", target=execution.application_url), Step(kind="verify", target=execution.application_url)],
        fixture_pages=pages
        or {
            "open": "<html><title>Apply</title><body>form</body></html>",
            "verify": "<html><title>Done</title><body>Your application has been submitted.</body></html>",
        },
    )


def _make(job_key, url="https://example.com/apply"):
    return ApplicationExecution(
        job_key=job_key,
        company="Acme",
        title="Support Engineer",
        application_url=url,
        pipeline={"profile": {"email": "ada@example.com"}, "fields": [], "resume_path": "/tmp/r.pdf"},
    )


def test_restart_resumes_from_queued_state(tmp_path):
    """An interrupted application resumes safely after restart."""
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    exc = _make("job-r")
    store.save(exc)
    machine.advance_to_ready(exc)
    machine.approve(exc)
    machine.queue(exc)
    store.save(exc)
    assert exc.status == ExecutionStatus.QUEUED

    # Simulate a process restart: a fresh store instance reads the same files.
    store2 = ExecutionStore(tmp_path)
    runner = ApplicationBatchRunner(
        store2,
        ApplicationExecutionStateMachine(store2),
        plan_builder=_fixture_plan_submit,
    )

    loaded = store2.list()[0]
    assert loaded.status == ExecutionStatus.QUEUED
    outcome = _run(runner.execute_batch([loaded]))
    assert outcome.submitted == 1
    assert store2.by_job_key("job-r")[0].status == ExecutionStatus.SUBMISSION_VERIFIED


def test_idempotent_batch_does_not_double_submit(tmp_path):
    """Running the same queued batch twice must not re-submit already-verified jobs."""
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    exc = _make("job-i")
    store.save(exc)
    machine.advance_to_ready(exc)
    machine.approve(exc)
    store.save(exc)

    runner = ApplicationBatchRunner(
        store,
        machine,
        plan_builder=_fixture_plan_submit,
    )

    queued = runner.queue_batch([exc])
    first = _run(runner.execute_batch(queued))
    assert first.submitted == 1
    # Re-running against the now-verified execution must not re-submit.
    queued_again = runner.queue_batch([store.by_job_key("job-i")[0]])
    assert queued_again == []
    second = _run(runner.execute_batch(queued_again))
    assert second.submitted == 0
    assert store.by_job_key("job-i")[0].status == ExecutionStatus.SUBMISSION_VERIFIED


def test_isolated_failure_one_bad_job_does_not_abort_batch(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    good = _make("good")
    bad = _make("bad")
    store.save(good)
    store.save(bad)
    for exc in (good, bad):
        machine.advance_to_ready(exc)
        store.save(exc)

    for exc in (good, bad):
        machine.approve(exc)
        store.save(exc)

    def plan(execution):
        # 'bad' triggers a validation error, 'good' submits fine.
        pages = {
            "open": "<html><title>Apply</title><body>form</body></html>",
            "submit": (
                "<html><title>Error</title><body><span class='error'>Please correct fields</span></body></html>"
                if execution.job_key == "bad"
                else "<html><title>Done</title><body>Your application has been submitted.</body></html>"
            ),
        }
        return ApplicationPlan(
            execution_id=execution.execution_id,
            url=execution.application_url,
            profile={},
            fields=[],
            steps=[Step(kind="open", target=execution.application_url), Step(kind="click", target="submit"), Step(kind="verify", target=execution.application_url)],
            fixture_pages=pages,
        )

    runner = ApplicationBatchRunner(store, machine, plan_builder=plan)

    queued = runner.queue_batch([store.by_job_key("good")[0], store.by_job_key("bad")[0]])
    outcome = _run(runner.execute_batch(queued))
    assert outcome.submitted == 1
    assert outcome.failed == 1
    assert store.by_job_key("good")[0].status == ExecutionStatus.SUBMISSION_VERIFIED
    assert store.by_job_key("bad")[0].status == ExecutionStatus.APPLICATION_FAILED


def test_state_api_dashboard_endpoint(tmp_path):
    from career_os.execution.state import ExecutionStore as ES

    store = ES(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    exc = _make("api-job")
    store.save(exc)
    machine.advance_to_ready(exc)
    store.save(exc)

    router = create_state_router(store=store)
    from fastapi import FastAPI

    api = FastAPI()
    api.include_router(router)
    client = TestClient(api)

    resp = client.get("/api/v1/state/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["totals"]["jobs_discovered"] == 1
    assert data["totals"]["awaiting_approval"] == 1

    execs = client.get("/api/v1/state/executions")
    assert execs.status_code == 200
    assert execs.json()["count"] == 1


def test_http_app_includes_state_router(tmp_path):
    from career_os.execution.state import ApplicationExecution as AE
    from career_os.execution.state import ApplicationExecutionStateMachine as ASM

    store = ExecutionStore(tmp_path)
    machine = ASM(store)
    exc = AE(job_key="app-job", company="Acme", title="Eng", application_url="https://e.com", pipeline={})
    store.save(exc)
    machine.advance_to_ready(exc)
    store.save(exc)

    # Point the mounted HTTP app's state router at this temp store so the
    # live endpoints are exercised end-to-end without touching project state.
    from fastapi import FastAPI

    from career_os.state_api import create_state_router

    api = FastAPI()
    api.include_router(create_state_router(store=store))
    client = TestClient(api)
    resp = client.get("/api/v1/state/dashboard")
    assert resp.status_code == 200
    assert resp.json()["totals"]["jobs_discovered"] == 1
