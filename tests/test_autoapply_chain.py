"""End-to-end tests for the dedicated auto-apply adapter and its state wiring.

These use synthetic/local fixtures and a deterministic driver only - no real
employer is ever contacted. They exercise the full contract states the adapter
must distinguish: SUBMITTED / SUBMISSION_VERIFIED / NEEDS_REVIEW /
AUTH_REQUIRED / BLOCKED_SECURITY_CHALLENGE / UNSUPPORTED / FAILED, plus
idempotent retry and restart-safe persistence.
"""

from __future__ import annotations

import asyncio

import pytest

from career_os.autoapply.adapter import AutoApplyAdapter, detect_application_flow
from career_os.execution.engine import ApplicationExecutor, Step
from career_os.execution.flow import FlowKind
from career_os.execution.runner import ApplicationBatchRunner, ApplicationPlan
from career_os.execution.state import (
    ApplicationExecution,
    ApplicationExecutionStateMachine,
    ExecutionStatus,
    ExecutionStore,
)


def _run(coro):
    return asyncio.run(coro)


def _make_execution(
    job_key: str = "job-1",
    application_url: str = "https://boards.greenhouse.io/acme/jobs/1",
    status: str = ExecutionStatus.DISCOVERED,
) -> ApplicationExecution:
    return ApplicationExecution(
        job_key=job_key,
        company="Acme",
        title="Support Engineer",
        application_url=application_url,
        status=status,
        pipeline={
            "profile": {"first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com"},
            "fields": [
                {"key": "first_name", "input_type": "text", "label": "First name"},
                {"key": "email", "input_type": "text", "label": "Email"},
            ],
            "resume_path": "/tmp/resume.pdf",
        },
    )


_SUBMISSION_PAGE = (
    "<html><title>Thank you</title><body>"
    "Your application has been submitted successfully. Reference ABC-123."
    "</body></html>"
)


def _approved(store, machine, execution):
    store.save(execution)
    machine.advance_to_ready(execution)
    store.save(execution)
    machine.approve(execution)
    store.save(execution)
    return execution


# ---------------------------------------------------------------------------
# Flow classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url,kind,supported",
    [
        ("https://boards.greenhouse.io/acme/jobs/1", FlowKind.GREENHOUSE, True),
        ("https://jobs.lever.co/acme/xyz", FlowKind.LEVER, True),
        ("https://jobs.ashbyhq.com/acme/123", FlowKind.ASHBY, True),
        ("https://acme.workable.com/jobs/1", FlowKind.GENERIC_FORM, True),
        ("https://jobs.smartrecruiters.com/oneclick/xyz", FlowKind.GENERIC_FORM, True),
        ("https://example.com/careers/apply", FlowKind.GENERIC_FORM, True),
        ("https://strange.example/job/1", FlowKind.UNKNOWN, False),
        ("", FlowKind.UNKNOWN, False),
    ],
)
def test_flow_detection(url, kind, supported):
    flow = detect_application_flow(url)
    assert flow.kind is kind
    assert flow.supported is supported


# ---------------------------------------------------------------------------
# Adapter structured results
# ---------------------------------------------------------------------------

def test_adapter_returns_verified_for_supported_flow(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    execution = _approved(store, machine, _make_execution())
    machine.queue(execution)
    store.save(execution)

    from career_os.execution.engine import DeterministicFixtureDriver

    adapter = AutoApplyAdapter(
        executor=ApplicationExecutor(driver=DeterministicFixtureDriver()),
        plan_builder=lambda ex: ApplicationPlan(
            execution_id=ex.execution_id,
            url=ex.application_url,
            profile=ex.pipeline.get("profile", {}),
            fields=ex.pipeline.get("fields", []),
            steps=[Step(kind="click", target="submit"), Step(kind="wait")],
            fixture_pages={"0": "<html><body>form</body></html>", "1": _SUBMISSION_PAGE},
        ),
    )
    result = _run(adapter.apply(execution))
    assert result.submitted is True
    assert result.verified is True
    assert result.unsupported is False
    assert result.status == ExecutionStatus.SUBMISSION_VERIFIED
    assert result.flow is not None and result.flow.kind is FlowKind.GREENHOUSE


def test_adapter_returns_unsupported_for_unknown_flow(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    execution = _approved(
        store, machine, _make_execution(application_url="https://strange.example/job/1")
    )
    machine.queue(execution)
    store.save(execution)

    adapter = AutoApplyAdapter()
    result = _run(adapter.apply(execution))
    assert result.unsupported is True
    assert result.submitted is False
    assert result.status == ExecutionStatus.UNSUPPORTED
    assert result.flow is not None and result.flow.kind is FlowKind.UNKNOWN


def test_adapter_never_submits_unsupported_flow():
    # The adapter must short-circuit before the engine runs for unknown flows.
    class ExplodingExecutor:
        async def run(self, **kwargs):
            raise AssertionError("engine must not be reached for unsupported flow")

    adapter = AutoApplyAdapter(executor=ExplodingExecutor())  # type: ignore[arg-type]
    execution = ApplicationExecution(application_url="https://strange.example/job/1")
    result = _run(adapter.apply(execution))
    assert result.unsupported is True


# ---------------------------------------------------------------------------
# Runner state wiring
# ---------------------------------------------------------------------------

def test_runner_marks_unsupported_for_unknown_url(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    runner = ApplicationBatchRunner(store, machine)

    execution = _make_execution(application_url="https://strange.example/job/1")
    store.save(execution)
    machine.advance_to_ready(execution)
    store.save(execution)
    approved = runner.approve_batch([execution])
    queued = runner.queue_batch(approved)

    outcome = _run(runner.execute_batch(queued))
    assert outcome.unsupported == 1
    assert outcome.submitted == 0
    assert outcome.failed == 0
    persisted = store.by_job_key("job-1")[0]
    assert persisted.status == ExecutionStatus.UNSUPPORTED


def test_runner_full_lifecycle_verified(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    runner = ApplicationBatchRunner(store, machine)

    execution = _make_execution()
    store.save(execution)
    machine.advance_to_ready(execution)
    store.save(execution)
    approved = runner.approve_batch([execution])
    queued = runner.queue_batch(approved)
    runner.plan_builder = lambda ex: ApplicationPlan(
        execution_id=ex.execution_id,
        url=ex.application_url,
        profile=ex.pipeline.get("profile", {}),
        fields=ex.pipeline.get("fields", []),
        steps=[Step(kind="click", target="submit"), Step(kind="wait")],
        fixture_pages={"0": "<html><body>form</body></html>", "1": _SUBMISSION_PAGE},
    )

    outcome = _run(runner.execute_batch(queued))
    assert outcome.submitted == 1
    assert outcome.verified == 1
    assert store.by_job_key("job-1")[0].status == ExecutionStatus.SUBMISSION_VERIFIED


def test_runner_auth_wall_marks_auth_required(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    runner = ApplicationBatchRunner(store, machine)

    execution = _make_execution(application_url="https://example.com/apply")
    store.save(execution)
    machine.advance_to_ready(execution)
    store.save(execution)
    approved = runner.approve_batch([execution])
    queued = runner.queue_batch(approved)

    class AuthDriver:
        async def step(self, action, state):
            return {
                "state": {
                    **state,
                    "page_html": "<html><title>Sign in</title><body>Please sign in to apply</body></html>",
                    "page_text": "Please sign in to apply",
                    "page_title": "Sign in",
                }
            }

    runner.executor = ApplicationExecutor(driver=AuthDriver())  # type: ignore[assignment]
    outcome = _run(runner.execute_batch(queued))
    assert outcome.auth_required == 1
    persisted = store.by_job_key("job-1")[0]
    assert persisted.status == ExecutionStatus.AUTH_REQUIRED


# ---------------------------------------------------------------------------
# Idempotency & durability
# ---------------------------------------------------------------------------

def test_already_completed_execution_is_skipped(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    runner = ApplicationBatchRunner(store, machine)

    execution = _make_execution()
    store.save(execution)
    machine.advance_to_ready(execution)
    machine.approve(execution)
    machine.queue(execution)
    machine.mark_submitted(execution, "reference ABC-123")
    machine.verify_submission(execution, "reference ABC-123")
    store.save(execution)

    # Re-running a batch must not re-apply a VERIFIED execution.
    outcome = _run(runner.execute_batch([execution]))
    assert outcome.skipped == 1
    assert outcome.submitted == 0
    persisted = store.by_job_key("job-1")[0]
    assert persisted.status == ExecutionStatus.SUBMISSION_VERIFIED


def test_state_survives_restart(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    execution = _make_execution(application_url="https://strange.example/job/1")
    store.save(execution)
    machine.advance_to_ready(execution)
    machine.approve(execution)
    machine.queue(execution)
    machine.unsupported(execution, "no flow")
    store.save(execution)

    # New store/machine over the same files simulates a process restart.
    store2 = ExecutionStore(tmp_path)
    reloaded = store2.by_job_key("job-1")[0]
    assert reloaded.status == ExecutionStatus.UNSUPPORTED
    assert reloaded.execution.get("unsupported")


def test_all_contract_statuses_are_serializable(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    for status, apply in [
        (ExecutionStatus.SUBMISSION_VERIFIED, lambda e: (
            machine.mark_submitted(e, "ref"), machine.verify_submission(e, "ref")
        )),
        (ExecutionStatus.AUTH_REQUIRED, lambda e: machine.auth_required(e, "login")),
        (ExecutionStatus.UNSUPPORTED, lambda e: machine.unsupported(e, "no flow")),
        (ExecutionStatus.BLOCKED_SECURITY_CHALLENGE, lambda e: machine.block_security_challenge(e, "captcha")),
        (ExecutionStatus.NEEDS_REVIEW, lambda e: machine.needs_review(e, "manual")),
        (ExecutionStatus.APPLICATION_FAILED, lambda e: machine.fail(e, "boom")),
    ]:
        execution = _make_execution(job_key=f"j-{status}")
        store.save(execution)
        machine.advance_to_ready(execution)
        machine.approve(execution)
        apply(execution)
        store.save(execution)
        reloaded = store.by_job_key(f"j-{status}")[0]
        assert reloaded.status == status
        assert reloaded.status in dir(ExecutionStatus)
