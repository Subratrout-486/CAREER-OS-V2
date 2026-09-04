from __future__ import annotations

import asyncio

from career_os.execution.auth import detect_auth_required
from career_os.execution.engine import (
    ApplicationExecutor,
    ExecutionResult,
    Step,
)
from career_os.execution.runner import ApplicationBatchRunner
from career_os.execution.state import (
    ApplicationExecution,
    ExecutionStatus,
    ExecutionStore,
)


def _await(coro):
    return asyncio.run(coro)


def _login_wall_html() -> str:
    return (
        "<html><head><title>Sign in to apply</title></head><body>"
        "Please sign in to continue your application."
        "<form><input type='email' name='email'><input type='password' name='password'>"
        "<button>Log in</button></form></body></html>"
    )


def _application_html() -> str:
    return (
        "<html><head><title>Apply Now</title></head><body>"
        "<form><input name='name'><button>Submit application</button></form>"
        "</body></html>"
    )


def _submission_html() -> str:
    return (
        "<html><head><title>Thank you</title></head><body>"
        "Your application has been submitted successfully. Reference 1234."
        "</body></html>"
    )


def test_detect_auth_required_login_form() -> None:
    result = detect_auth_required(url="https://x.test/apply", html=_login_wall_html())
    assert result.required
    assert "login_form_present" in result.signals
    assert "authentication required" in result.detail.casefold()


def test_detect_auth_required_text_signal() -> None:
    result = detect_auth_required(url="https://x.test/apply", text="You must sign in to apply.")
    assert result.required
    assert any("sign" in signal or "in" in signal for signal in result.signals)


def test_detect_auth_required_url_hint_and_status() -> None:
    result = detect_auth_required(url="https://x.test/login", http_status=401)
    assert result.required
    assert "login_url_hint" in result.signals
    assert "http_status_401" in result.signals


def test_detect_auth_required_passive_not_wall() -> None:
    html = (
        "<html><body><form><input type='password' placeholder='New password'>"
        "<button>Create a password</button></form></body></html>"
    )
    result = detect_auth_required(url="https://x.test/register", html=html)
    assert not result.required


def test_engine_blocks_on_auth_wall_never_submits() -> None:
    executor = ApplicationExecutor()
    result = _await(
        executor.run(
            url="https://x.test/apply",
            profile={"full_name": "A B"},
            fields=[{"key": "name", "input_type": "text"}],
            steps=[
                Step(kind="fill", target="name"),
                Step(kind="click", target="submit"),
                Step(kind="wait"),
            ],
            fixture_pages={"0": _login_wall_html(), "1": _login_wall_html()},
        )
    )
    assert isinstance(result, ExecutionResult)
    assert result.submitted is False
    assert result.auth_required is True
    assert result.security_blocked is False
    assert result.state == "auth_required"
    assert not result.evidence


def test_engine_does_not_treat_auth_as_security_challenge() -> None:
    executor = ApplicationExecutor()
    result = _await(
        executor.run(
            url="https://x.test/apply",
            profile={},
            fields=[],
            steps=[],
            fixture_pages={"0": _login_wall_html()},
        )
    )
    assert result.auth_required is True
    assert result.security_blocked is False
    assert result.challenge is None


def test_runner_surfaces_auth_as_distinct_state(tmp_path) -> None:
    store = ExecutionStore(tmp_path)
    machine = __import__(
        "career_os.execution.state", fromlist=["ApplicationExecutionStateMachine"]
    ).ApplicationExecutionStateMachine(store)
    execution = ApplicationExecution(
        job_key="job-1",
        application_url="https://x.test/apply",
        status=ExecutionStatus.READY_FOR_APPROVAL,
    )
    machine.approve(execution)
    machine.queue(execution)

    class AuthDriver:
        async def step(self, action, state):
            return {
                "state": {
                    **state,
                    "page_html": _login_wall_html(),
                    "page_text": "Please sign in to apply.",
                    "page_title": "Sign in",
                }
            }

    runner = ApplicationBatchRunner(
        store=store,
        machine=machine,
        executor=ApplicationExecutor(driver=AuthDriver()),
        plan_builder=lambda e: __import__(
            "career_os.execution.runner", fromlist=["ApplicationPlan"]
        ).ApplicationPlan(
            execution_id=e.execution_id, url=e.application_url, profile={}, fields=[], steps=[]
        ),
    )
    outcome = _await(runner.execute_batch([execution]))
    assert outcome.auth_required == 1
    assert outcome.failed == 0
    assert outcome.blocked_security == 0
    persisted = store.load(execution.execution_id)
    assert persisted is not None
    assert persisted.status == ExecutionStatus.AUTH_REQUIRED
    assert (
        "authentication" in persisted.execution.get("auth_required", "").casefold()
        or "authentication" in persisted.events[-1].detail.casefold()
    )
