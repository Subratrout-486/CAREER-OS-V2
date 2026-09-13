"""Real-Playwright integration tests against local HTML fixtures.

These tests exercise the actual browser driver (not the deterministic fallback)
using an in-process HTTP server that serves plain HTML forms. No employer site
and no anti-bot system is ever contacted. They require Chromium (installed by
the devcontainer / CI: ``python -m playwright install chromium``).
"""

from __future__ import annotations

import asyncio
import functools
import http.server
import os
import socketserver
import threading

import pytest

from career_os.execution.engine import ApplicationExecutor, Step
from career_os.execution.state import (
    ApplicationExecution,
    ApplicationExecutionStateMachine,
    ExecutionStatus,
    ExecutionStore,
)


def _run(coro):
    return asyncio.run(coro)


_APPLICATION_PAGE = """<!doctype html><html><head><title>Apply to Acme</title></head>
<body>
<h1>Application form</h1>
<form action="/submit" method="post">
  <label for="first">First name</label>
  <input id="first" name="first_name" type="text" required>
  <label for="last">Last name</label>
  <input id="last" name="last_name" type="text" required>
  <label for="mail">Email address</label>
  <input id="mail" name="email" type="email" required>
  <label for="cv">Attach resume</label>
  <input id="cv" name="resume" type="file">
  <label for="wa">Work authorization</label>
  <select id="wa" name="work_authorization"><option>No</option><option>Yes</option></select>
  <button type="submit" id="submit">Submit application</button>
</form>
<script>
  document.querySelector("form").addEventListener("submit", function (e) {
    e.preventDefault();
    window.location.href = "/confirm?ref=REF-ACME-42";
  });
</script>
</body></html>"""

_SUBMISSION_PAGE = """<!doctype html><html><head><title>Application received</title></head>
<body>
<h1>Thank you</h1>
<p>Your application has been submitted. Reference REF-ACME-42</p>
</body></html>"""

_VALIDATION_PAGE = """<!doctype html><html><head><title>Application form</title></head>
<body>
<p class="error">Please correct the highlighted fields</p>
<form action="/submit" method="post">
  <label for="first">First name</label><input id="first" name="first_name" type="text" required>
  <input type="submit">
</form>
</body></html>"""

_CAPTCHA_PAGE = """<!doctype html><html><head><title>Verify your identity</title></head>
<body><div class="g-recaptcha"></div><p>Please verify you are not a robot.</p></body></html>"""

_AUTH_PAGE = """<!doctype html><html><head><title>Sign in</title></head>
<body><form><label for="u">Email</label><input id="u" name="email">
<label for="p">Password</label><input id="p" name="password" type="password"></form></body></html>"""


class _Handler(http.server.BaseHTTPRequestHandler):
    pages: dict[str, str] = {}

    def do_GET(self):  # noqa: N802
        import re

        self._reply(self.path)

    def do_POST(self):  # noqa: N802
        self._reply(self.path)

    def _reply(self, path: str) -> None:
        import re

        path = re.sub(r"\?.*", "", str(path))
        html = self.pages.get(path)
        if html is None:
            self.send_response(404)
            self.end_headers()
            return
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # noqa: D102
        pass


@pytest.fixture()
def browser_pages():
    handler = functools.partial(_Handler)
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        _Handler.pages = {
            "/apply": _APPLICATION_PAGE,
            "/confirm": _SUBMISSION_PAGE,
            "/validate": _VALIDATION_PAGE,
            "/submit": _VALIDATION_PAGE,  # form POST target keeps the marker visible
            "/captcha": _CAPTCHA_PAGE,
            "/login": _AUTH_PAGE,
        }
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _profile():
    return {
        "first_name": "Subrat",
        "last_name": "Rout",
        "email": "subrat@example.com",
        "candidate": {"name": "Subrat Rout", "work_authorization": "Yes"},
    }


@pytest.fixture()
def browser_env(monkeypatch):
    """Enable the live browser driver for the duration of one test only."""
    monkeypatch.setenv("CAREER_OS_ENABLE_BROWSER", "1")
    monkeypatch.setenv("APPLICATION_BROWSER_HEADLESS", "1")
    return


def test_persistent_single_session_multi_step_flow(browser_pages, browser_env, tmp_path):
    """One browser session fills, uploads, submits and verifies in sequence."""
    resume = tmp_path / "Subrat_Rout_Support_Engineer.pdf"
    resume.write_bytes(b"%PDF-1.4 test artifact")

    from career_os.execution.playwright_driver import PlaywrightExecutionDriver

    driver = PlaywrightExecutionDriver(timeout_ms=15_000)
    executor = ApplicationExecutor(driver=driver)

    async def scenario():
        try:
            return await executor.run(
                url=f"{browser_pages}/apply",
                profile=_profile(),
                fields=[],  # dynamic field discovery on the live page
                steps=[Step(kind="open", target=f"{browser_pages}/apply")],
                resume_path=str(resume),
            )
        finally:
            await driver.close()

    result = _run(scenario())

    assert result.submitted is True
    assert result.state == "submitted"  # runner persists this via verify_submission
    assert "first_name" in result.details["filled"]
    assert "last_name" in result.details["filled"]
    # Resume artifact upload hit the real file input.
    assert "resume" in result.details["uploaded"]
    # URL transitioned to the confirmation page and the reference was captured.
    assert "REF-ACME-42" in "; ".join(result.evidence)


def test_real_browser_session_is_reused_across_steps(browser_pages, browser_env):
    """assert the same page object handles open->fill->select->... (no relaunch)."""
    from career_os.execution.playwright_driver import PlaywrightExecutionDriver

    driver = PlaywrightExecutionDriver(timeout_ms=15_000)

    async def scenario() -> None:
        state: dict[str, object] = {}
        state = (await driver.step({"kind": "open", "target": f"{browser_pages}/apply"}, state))["state"]
        # The driver keeps its own self._page; steps after open must succeed
        # within the same alive event loop (Playwright objects are loop-bound).
        out1 = await driver.step({"kind": "fill", "target": "first_name", "value": "Subrat"}, state)
        assert out1["state"]["filled"] == ["first_name"]
        out2 = await driver.step({"kind": "fill", "target": "last_name", "value": "Rout"}, out1["state"])
        assert "last_name" in out2["state"]["filled"]
        out3 = await driver.step({"kind": "select", "target": "work_authorization", "value": "Yes"}, out2["state"])
        assert "work_authorization" in out3["state"]["filled"]
        final = await driver.step({"kind": "verify", "target": f"{browser_pages}/confirm"}, out3["state"])
        assert final.get("state", {}).get("page_title") in {"", "Apply to Acme"}
        # verify closes the session -> a single persistent page was used
        assert driver._page is None
        await driver.close()

    _run(scenario())


def test_real_browser_field_not_found_is_explicit_error(browser_pages, browser_env):
    from career_os.execution.playwright_driver import PlaywrightExecutionDriver

    driver = PlaywrightExecutionDriver(timeout_ms=10_000)

    async def scenario() -> None:
        state: dict[str, object] = {}
        state = (await driver.step({"kind": "open", "target": f"{browser_pages}/apply"}, state))["state"]
        outcome = await driver.step(
            {"kind": "fill", "target": "does_not_exist", "value": "x"},
            state,
        )
        assert "error" in outcome
        assert "field not found" in outcome["error"]
        await driver.close()

    _run(scenario())


def _run_engine_result(driver, url, profile=None):
    """Run the engine against a live page, always closing the session on the same loop."""

    async def scenario():
        try:
            return await ApplicationExecutor(driver=driver).run(
                url=url,
                profile=profile or _profile(),
                fields=[],
                steps=[Step(kind="open", target=url)],
            )
        finally:
            await driver.close()

    return _run(scenario())


def test_real_browser_validation_error_detected(browser_pages, browser_env):
    from career_os.execution.playwright_driver import PlaywrightExecutionDriver

    driver = PlaywrightExecutionDriver(timeout_ms=15_000)
    # The engine opens the page itself and detects the validation marker
    # after a submit click, within a single event loop.
    result = _run_engine_result(driver, f"{browser_pages}/validate")
    assert result.state == "validation_error"
    assert result.submitted is False


def test_browser_engine_stops_on_captcha(browser_pages, browser_env):
    from career_os.execution.playwright_driver import PlaywrightExecutionDriver

    driver = PlaywrightExecutionDriver(timeout_ms=15_000)
    result = _run_engine_result(driver, f"{browser_pages}/captcha")
    assert result.submitted is False
    assert result.security_blocked is True
    assert result.state == "blocked_security_challenge"


def test_browser_engine_stops_on_auth_required(browser_pages, browser_env):
    from career_os.execution.playwright_driver import PlaywrightExecutionDriver

    driver = PlaywrightExecutionDriver(timeout_ms=15_000)
    result = _run_engine_result(driver, f"{browser_pages}/login")
    assert result.submitted is False
    assert result.auth_required is True
    assert result.state == "auth_required"


def test_browser_runner_persists_verified_state(browser_pages, browser_env, tmp_path):
    from career_os.execution.playwright_driver import PlaywrightExecutionDriver
    from career_os.execution.runner import ApplicationBatchRunner, ApplicationPlan

    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    driver = PlaywrightExecutionDriver(timeout_ms=15_000)
    runner = ApplicationBatchRunner(
        store, machine, executor=ApplicationExecutor(driver=driver)
    )
    execution = ApplicationExecution(
        job_key="job-1",
        company="Acme",
        title="Support Engineer",
        application_url=f"{browser_pages}/apply",
        pipeline={"profile": _profile(), "fields": [], "resume_path": None},
    )
    store.save(execution)
    machine.advance_to_ready(execution)
    store.save(execution)
    approved = runner.approve_batch([execution])
    assert len(approved) == 1
    queued = runner.queue_batch(approved)
    assert len(queued) == 1

    resume = tmp_path / "Subrat_Rout_Support_Engineer.pdf"
    resume.write_bytes(b"%PDF-1.4 test artifact")

    def plan(ex):
        return ApplicationPlan(
            execution_id=ex.execution_id,
            url=ex.application_url,
            profile=ex.pipeline.get("profile", {}),
            fields=ex.pipeline.get("fields", []),
            resume_path=str(resume),
            steps=[Step(kind="open", target=ex.application_url)],
        )

    runner.plan_builder = plan

    async def scenario():
        try:
            return await runner.execute_batch(queued)
        finally:
            await driver.close()

    outcome = _run(scenario())
    assert outcome.submitted == 1
    assert outcome.verified == 1
    assert store.by_job_key("job-1")[0].status == ExecutionStatus.SUBMISSION_VERIFIED