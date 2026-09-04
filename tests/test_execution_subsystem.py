"""Tests for the durable, approval-gated application execution subsystem.

These use synthetic/local fixtures only. No real employer is ever contacted.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from career_os.execution.challenge import detect_challenge
from career_os.execution.engine import Step
from career_os.execution.runner import (
    ApplicationBatchRunner,
    ApplicationPlan,
)
from career_os.execution.state import (
    ApplicationExecution,
    ApplicationExecutionStateMachine,
    ExecutionStatus,
    ExecutionStore,
    ExecutionTransitionError,
)


def _run(coro):
    return asyncio.run(coro)


def _make_execution(job_key: str = "job-1", application_url: str = "https://example.com/apply") -> ApplicationExecution:
    return ApplicationExecution(
        job_key=job_key,
        company="Acme",
        title="Support Engineer",
        application_url=application_url,
        pipeline={
            "profile": {"first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com"},
            "fields": [
                {"key": "first_name", "input_type": "text", "label": "First name"},
                {"key": "email", "input_type": "text", "label": "Email"},
            ],
            "resume_path": "/tmp/resume.pdf",
        },
    )


def test_approval_gate_blocks_unapproved_execution(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    exc = _make_execution()
    store.save(exc)

    machine.advance_to_ready(exc)
    store.save(exc)
    # Not approved -> cannot queue/execute
    assert not machine.should_execute(exc)
    with pytest.raises(ExecutionTransitionError):
        machine.queue(exc)


def test_advance_to_ready_and_approve(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    exc = _make_execution()
    store.save(exc)

    machine.advance_to_ready(exc)
    store.save(exc)
    assert exc.status == ExecutionStatus.READY_FOR_APPROVAL

    machine.approve(exc)
    store.save(exc)
    assert exc.status == ExecutionStatus.APPROVED
    assert exc.approval.get("approved") is True
    assert machine.should_execute(exc)


def test_approval_requires_ready_for_approval(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    exc = _make_execution()
    # status is DISCOVERED
    with pytest.raises(ExecutionTransitionError):
        machine.approve(exc)


def test_submission_requires_evidence(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    exc = _make_execution()
    machine.advance_to_ready(exc)
    machine.approve(exc)
    with pytest.raises(ExecutionTransitionError):
        machine.mark_submitted(exc, "   ")


def test_state_round_trip_survives_restart(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    exc = _make_execution()
    store.save(exc)
    machine.advance_to_ready(exc)
    machine.approve(exc)
    store.save(exc)

    # simulate restart: new store/machine reading same files
    store2 = ExecutionStore(tmp_path)
    loaded = store2.list()[0]
    assert loaded.status == ExecutionStatus.APPROVED
    assert loaded.events[-1].status == ExecutionStatus.APPROVED


def test_full_lifecycle_via_runner(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    runner = ApplicationBatchRunner(store, machine)

    exc = _make_execution()
    store.save(exc)
    machine.advance_to_ready(exc)
    store.save(exc)

    approved = runner.approve_batch([exc])
    assert len(approved) == 1
    queued = runner.queue_batch(approved)
    assert len(queued) == 1

    # Provide fixture pages and a deterministic plan
    runner.plan_builder = lambda ex: ApplicationPlan(
        execution_id=ex.execution_id,
        url=ex.application_url,
        profile=ex.pipeline.get("profile", {}),
        fields=ex.pipeline.get("fields", []),
        resume_path=ex.pipeline.get("resume_path"),
        steps=[
            Step(kind="fill", target="first_name"),
            Step(kind="fill", target="email"),
            Step(kind="click", target="submit"),
            Step(kind="wait"),
        ],
        fixture_pages={
            "open": "<html><title>Apply</title><body>first name</body></html>",
            "submit": "<html><title>Done</title><body>Thank you, your application has been submitted. Reference: ABC-123</body></html>",
        },
    )

    outcome = _run(runner.execute_batch(queued))
    assert outcome.submitted == 1
    assert outcome.verified == 1

    final = store.by_job_key("job-1")[0]
    assert final.status == ExecutionStatus.SUBMISSION_VERIFIED


def test_security_challenge_stops_execution(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    runner = ApplicationBatchRunner(store, machine)

    exc = _make_execution()
    store.save(exc)
    machine.advance_to_ready(exc)
    store.save(exc)
    approved = runner.approve_batch([exc])
    queued = runner.queue_batch(approved)

    runner.plan_builder = lambda ex: ApplicationPlan(
        execution_id=ex.execution_id,
        url=ex.application_url,
        profile=ex.pipeline.get("profile", {}),
        fields=ex.pipeline.get("fields", []),
        steps=[Step(kind="open", target=ex.application_url)],
        fixture_pages={
            "open": "<html><title>Verify you are human</title><body><div class='g-recaptcha'></div>captcha protected</body></html>",
        },
    )

    outcome = _run(runner.execute_batch(queued))
    assert outcome.blocked_security == 1
    assert outcome.submitted == 0

    final = store.by_job_key("job-1")[0]
    assert final.status == ExecutionStatus.BLOCKED_SECURITY_CHALLENGE
    assert "captcha" in final.execution.get("security_challenge", "").casefold()


def test_validation_error_fails_application(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    runner = ApplicationBatchRunner(store, machine)

    exc = _make_execution()
    store.save(exc)
    machine.advance_to_ready(exc)
    store.save(exc)
    approved = runner.approve_batch([exc])
    queued = runner.queue_batch(approved)

    runner.plan_builder = lambda ex: ApplicationPlan(
        execution_id=ex.execution_id,
        url=ex.application_url,
        profile=ex.pipeline.get("profile", {}),
        fields=ex.pipeline.get("fields", []),
        steps=[Step(kind="click", target="submit")],
        fixture_pages={
            "open": "<html><title>Apply</title><body>form</body></html>",
            "submit": "<html><title>Apply</title><body><span class='error'>Please correct the highlighted fields</span></body></html>",
        },
    )

    outcome = _run(runner.execute_batch(queued))
    assert outcome.submitted == 0
    assert outcome.failed == 1
    assert store.by_job_key("job-1")[0].status == ExecutionStatus.APPLICATION_FAILED


def test_detect_challenge_detects_captcha_markers():
    detection = detect_challenge(
        url="https://example.com/jobs/1/apply",
        title="Security Check",
        text="We need to verify you are human before continuing.",
        html="<div class='g-recaptcha'></div>",
    )
    assert detection.blocked is True
    assert detection.kind == "reCAPTCHA"


def test_detect_challenge_clean_page_not_blocked():
    detection = detect_challenge(
        url="https://example.com/apply",
        title="Application Form",
        text="First name, last name, email",
    )
    assert detection.blocked is False
    assert detection.kind is None


def test_auto_approve_allows_execution():
    store = ExecutionStore(Path("/tmp/nonexistent"))
    machine = ApplicationExecutionStateMachine(store, auto_approve=True)
    exc = _make_execution()
    # Even with auto_approve, must reach ready first
    machine.advance_to_ready(exc)
    machine.approve(exc)
    assert machine.should_execute(exc)
