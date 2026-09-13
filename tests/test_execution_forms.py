"""Tests for dynamic form discovery, verified field mapping, and engine auto-discovery.

Uses synthetic HTML fixtures only - no real employer is ever contacted and no
CAPTCHA or anti-bot system is exercised.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from career_os.execution.engine import ApplicationExecutor, Step
from career_os.execution.forms import (
    discover_fields,
    map_discovered_fields,
)
from career_os.execution.state import (
    ApplicationExecution,
    ApplicationExecutionStateMachine,
    ExecutionStatus,
    ExecutionStore,
)
from career_os.execution.runner import ApplicationBatchRunner, ApplicationPlan


def _run(coro):
    return asyncio.run(coro)


_FORM_HTML = """
<html><head><title>Apply now</title></head><body>
<form>
  <label for="first">First name</label><input id="first" name="first_name" type="text" required>
  <label for="last">Last name</label><input id="last" name="last_name" type="text" required>
  <label for="mail">Email address</label><input id="mail" name="email" type="email" required>
  <label for="cv">Attach resume</label><input id="cv" name="resume" type="file" required>
  <label for="wa">Work authorization</label>
  <select id="wa" name="work_authorization" required>
    <option>Please select</option><option>Yes</option><option>No</option>
  </select>
  <input type="hidden" name="csrf" value="x">
  <input type="submit" value="Submit application">
</form>
</body></html>
"""

_CONFIRMATION_HTML = (
    "<html><head><title>Thanks</title></head><body>"
    "Your application has been submitted. Reference ABC-123"
    "</body></html>"
)


def _profile() -> dict[str, object]:
    return {
        "first_name": "Subrat",
        "last_name": "Rout",
        "full_name": "Subrat Rout",
        "email": "subrat@example.com",
        "location": "Hyderabad, India",
        "candidate": {
            "name": "Subrat Rout",
            "location": "Hyderabad, India",
            "work_authorization": "Yes",
        },
    }


# ---------------------------------------------------------------------------
# discover_fields
# ---------------------------------------------------------------------------


def test_discover_fields_finds_controls_and_lines_up_labels():
    fields = discover_fields(_FORM_HTML)
    by_key = {f.key: f for f in fields}

    assert set(by_key) == {
        "first_name",
        "last_name",
        "email",
        "resume",
        "work_authorization",
    }
    assert by_key["first_name"].label == "First name"
    assert by_key["first_name"].required is True
    assert by_key["email"].input_type == "email"
    assert by_key["resume"].input_type == "file"
    assert by_key["resume"].value_hint == "resume"
    assert by_key["work_authorization"].input_type == "select"
    assert by_key["work_authorization"].options == ("Yes", "No")


def test_discover_fields_skips_non_form_input_types():
    html = """
    <input type="hidden" name="token">
    <input type="submit" value="Go">
    <input type="button" value="x">
    <input type="image" alt="go">
    <label for="q">Visible field</label><input id="q" name="q" type="text">
    """
    fields = discover_fields(html)
    assert [f.key for f in fields] == ["q"]


def test_discover_fields_uses_placeholder_and_aria_when_no_label():
    html = """
    <input name="company" placeholder="Current employer" required>
    <input name="linkedin" aria-label="LinkedIn profile URL">
    """
    fields = discover_fields(html)
    by_key = {f.key: f for f in fields}
    assert by_key["company"].placeholder == "Current employer"
    assert by_key["company"].required is True
    assert by_key["linkedin"].aria_label == "LinkedIn profile URL"


def test_discover_fields_handles_textarea():
    html = '<label for="bio">Tell us about yourself</label><textarea id="bio" name="bio"></textarea>'
    fields = discover_fields(html)
    assert fields[0].key == "bio"
    assert fields[0].input_type == "textarea"
    assert fields[0].label == "Tell us about yourself"


# ---------------------------------------------------------------------------
# map_discovered_fields
# ---------------------------------------------------------------------------


def test_map_resolves_verified_values_only():
    fields = discover_fields(_FORM_HTML)
    mapped = map_discovered_fields(fields, _profile())
    resolved = {m.field.key: m for m in mapped if m.resolved}
    assert resolved["first_name"].value == "Subrat"
    assert resolved["last_name"].value == "Rout"
    assert resolved["email"].value == "subrat@example.com"


def test_map_never_invents_a_missing_value():
    profile = {"first_name": "Subrat", "last_name": "Rout"}
    mapped = {m.field.key: m for m in map_discovered_fields(discover_fields(_FORM_HTML), profile)}
    # Email is required but absent from the Source of Truth -> NEVER fabricated.
    assert mapped["email"].resolved is False
    assert mapped["email"].review is True
    assert "no verified" in mapped["email"].reason


def test_map_optional_unknown_field_is_skipped_not_blocked():
    html = '<label for="ln">LinkedIn URL</label><input id="ln" name="linkedin_url" type="text">'
    mapped = map_discovered_fields(discover_fields(html), _profile())[0]
    assert mapped.optional is True
    assert mapped.resolved is False
    assert mapped.review is False


def test_map_required_unknown_field_becomes_review():
    html = '<label for="sc">Security clearance</label><input id="sc" name="clearance" type="text" required>'
    mapped = map_discovered_fields(discover_fields(html), _profile())[0]
    assert mapped.review is True
    assert mapped.resolved is False


def test_map_work_authorization_from_verified_value():
    html = (
        '<label for="wa">Work authorization</label>'
        '<select id="wa" name="work_authorization" required>'
        "<option>Please select</option><option>Yes</option><option>No</option></select>"
    )
    mapped = map_discovered_fields(
        discover_fields(html),
        {"candidate": {"work_authorization": "Yes", "name": "Subrat Rout"}},
    )[0]
    assert mapped.resolved is True
    assert mapped.value == "Yes"


def test_map_full_name_derived_from_verified_name():
    html = '<label for="fn">Full name</label><input id="fn" name="full_name" required>'
    mapped = map_discovered_fields(discover_fields(html), _profile())[0]
    assert mapped.resolved is True
    assert mapped.value == "Subrat Rout"


def test_map_location_resolved_from_profile():
    html = '<label for="loc">Location</label><input id="loc" name="location">'
    mapped = map_discovered_fields(discover_fields(html), _profile())[0]
    assert mapped.resolved is True
    assert mapped.value == "Hyderabad, India"


# ---------------------------------------------------------------------------
# engine auto-discovery
# ---------------------------------------------------------------------------


def test_engine_discovers_fields_and_submits(tmp_path):
    resume = tmp_path / "Subrat_Rout_Support_Engineer.pdf"
    resume.write_bytes(b"%PDF-1.4 test artifact")
    executor = ApplicationExecutor()
    result = _run(
        executor.run(
            url="https://boards.greenhouse.io/acme/jobs/1",
            profile=_profile(),
            fields=[],  # no pre-populated mapping -> dynamic discovery
            steps=[Step(kind="open", target="https://boards.greenhouse.io/acme/jobs/1")],
            resume_path=str(resume),
            fixture_pages={"open": _FORM_HTML, "confirm": _CONFIRMATION_HTML},
        )
    )
    assert result.submitted is True
    assert result.state == "submitted"
    assert "first_name" in result.details["filled"]
    assert "last_name" in result.details["filled"]
    assert isinstance(result.details["field_discovery"], list)  # serializable payload

def test_engine_portal_success_url_verifies_without_text_marker(tmp_path):
    """A recognized portal URL transition verifies even without a prose marker.

    The confirm page only says "Your candidacy has been recorded at Acme" -
    which _looks_submitted() does not classify as success - but the URL is a
    Greenhouse /application/confirmation transition, so portal verification
    carries the evidence.
    """
    resume = tmp_path / "Subrat_Rout_Support_Engineer.pdf"
    resume.write_bytes(b"%PDF-1.4 test artifact")
    executor = ApplicationExecutor()
    result = _run(
        executor.run(
            url="https://boards.greenhouse.io/acme/jobs/1",
            profile=_profile(),
            fields=[],
            # Explicit field steps keep the plan's click/wait/verify sequence; the
            # confirm step names the portal's /application/confirmation transition.
            steps=[
                Step(kind="open", target="https://boards.greenhouse.io/acme/jobs/1"),
                Step(kind="fill", target="first_name", value="Subrat"),
                Step(kind="click", target="submit"),
                Step(kind="wait"),
                Step(kind="verify", target="https://boards.greenhouse.io/apply/application/confirmation"),
            ],
            resume_path=str(resume),
            fixture_pages={
                "open": _FORM_HTML,
                "confirm": (
                    "<html><head><title>Done</title></head><body>"
                    "Your candidacy has been recorded at Acme</body></html>"
                ),
            },
        )
    )
    assert result.submitted is True
    assert result.state == "submitted"
    assert any("confirmation" in e for e in result.evidence)


def test_engine_captures_portal_reference_from_confirmation_page(tmp_path):
    """Portal reference codes on the confirmation page flow into evidence."""
    resume = tmp_path / "Subrat_Rout_Support_Engineer.pdf"
    resume.write_bytes(b"%PDF-1.4 test artifact")
    executor = ApplicationExecutor()
    result = _run(
        executor.run(
            url="https://jobs.lever.co/acme/support-eng/42",
            profile=_profile(),
            fields=[],
            steps=[
                Step(kind="open", target="https://jobs.lever.co/acme/support-eng/42"),
                Step(kind="fill", target="first_name", value="Subrat"),
                Step(kind="click", target="submit"),
                Step(kind="wait"),
                Step(kind="verify", target="https://jobs.lever.co/acme/42"),
            ],
            resume_path=str(resume),
            fixture_pages={
                "open": _FORM_HTML,
                "confirm": (
                    "<html><head><title>Application submitted</title></head><body>"
                    "Your application has been submitted. Application reference LV-9799."
                    "</body></html>"
                ),
            },
        )
    )
    assert result.submitted is True
    assert any("LV-9799" in e for e in result.evidence)

def test_engine_uploads_resume_when_artifact_exists(tmp_path):
    resume = tmp_path / "Subrat_Rout_Support_Engineer.pdf"
    resume.write_bytes(b"%PDF-1.4 test artifact")
    form = (
        '<label for="first">First name</label><input id="first" name="first_name" required>'
        '<label for="cv">Attach resume</label><input id="cv" name="resume" type="file" required>'
    )
    executor = ApplicationExecutor()
    result = _run(
        executor.run(
            url="https://boards.greenhouse.io/acme/jobs/1",
            profile=_profile(),
            fields=[],
            steps=[Step(kind="open", target="https://boards.greenhouse.io/acme/jobs/1")],
            resume_path=str(resume),
            fixture_pages={"open": form, "confirm": _CONFIRMATION_HTML},
        )
    )
    assert result.submitted is True
    assert "resume" in result.details["uploaded"]


def test_engine_needs_review_when_required_field_unresolved():
    form = (
        '<label for="first">First name</label><input id="first" name="first_name" required>'
        '<label for="sc">Security clearance</label><input id="sc" name="clearance" required>'
    )
    executor = ApplicationExecutor()
    result = _run(
        executor.run(
            url="https://boards.greenhouse.io/acme/jobs/1",
            profile=_profile(),
            fields=[],
            steps=[Step(kind="open", target="https://boards.greenhouse.io/acme/jobs/1")],
            fixture_pages={"open": form, "confirm": _CONFIRMATION_HTML},
        )
    )
    assert result.submitted is False
    assert result.state == "needs_review"
    assert any("clearance" in b for b in result.blockers)


def test_engine_requires_resume_for_required_file_input():
    form = '<label for="cv">Attach resume</label><input id="cv" name="resume" type="file" required>'
    executor = ApplicationExecutor()
    result = _run(
        executor.run(
            url="https://boards.greenhouse.io/acme/jobs/1",
            profile=_profile(),
            fields=[],
            steps=[Step(kind="open", target="https://boards.greenhouse.io/acme/jobs/1")],
            resume_path=None,
            fixture_pages={"open": form, "confirm": _CONFIRMATION_HTML},
        )
    )
    assert result.state == "needs_review"
    assert any("resume" in b.casefold() for b in result.blockers)


def test_engine_never_ignores_driver_error():
    class ErroringDriver:
        async def step(self, action, state):
            if action.get("kind") == "open":
                return {"state": state, "error": "network unreachable", "retryable": False}
            return {"state": state}

    executor = ApplicationExecutor(driver=ErroringDriver())
    result = _run(
        executor.run(
            url="https://example.com/apply",
            profile=_profile(),
            fields=[],
            steps=[Step(kind="open", target="https://example.com/apply")],
        )
    )
    assert result.submitted is False
    assert result.state == "error"
    assert "network unreachable" in result.blockers


def test_engine_stops_on_security_challenge_wall():
    form = (
        "<html><head><title>Verify you are human</title></head><body>"
        '<div class="g-recaptcha"></div><p>Please verify you are not a robot</p>'
        "</body></html>"
    )
    executor = ApplicationExecutor()
    result = _run(
        executor.run(
            url="https://example.com/apply",
            profile=_profile(),
            fields=[],
            steps=[Step(kind="open", target="https://example.com/apply")],
            fixture_pages={"open": form},
        )
    )
    assert result.submitted is False
    assert result.security_blocked is True
    assert result.state == "blocked_security_challenge"


def test_engine_stops_on_auth_required_wall():
    form = (
        "<html><head><title>Sign in</title></head><body>"
        '<form><label for="u">Email</label><input id="u" name="email">'
        '<label for="p">Password</label><input id="p" name="password" type="password">'
        "</form></body></html>"
    )
    executor = ApplicationExecutor()
    result = _run(
        executor.run(
            url="https://example.com/apply",
            profile=_profile(),
            fields=[],
            steps=[Step(kind="open", target="https://example.com/apply")],
            fixture_pages={"open": form},
        )
    )
    assert result.submitted is False
    assert result.auth_required is True
    assert result.state == "auth_required"


def test_engine_submission_unverified_when_click_without_confirmation():
    form = '<label for="first">First name</label><input id="first" name="first_name" required>'
    executor = ApplicationExecutor()
    result = _run(
        executor.run(
            url="https://example.com/apply",
            profile=_profile(),
            fields=[],
            steps=[Step(kind="open", target="https://example.com/apply")],
            fixture_pages={"open": form, "after": "<html><body>form still here</body></html>"},
        )
    )
    assert result.submitted is True  # submit action happened...
    assert result.state == "submission_unverified"  # ...but was never confirmed
    assert result.blockers


def test_engine_validation_error_blocks_submission():
    form = '<label for="first">First name</label><input id="first" name="first_name" required>'
    executor = ApplicationExecutor()
    result = _run(
        executor.run(
            url="https://example.com/apply",
            profile=_profile(),
            fields=[],
            steps=[Step(kind="open", target="https://example.com/apply")],
            fixture_pages={
                "open": form,
                "after": '<html><body><span class="error">Please correct the highlighted fields</span></body></html>',
            },
        )
    )
    assert result.submitted is False
    assert result.state == "validation_error"


def test_duplicate_submission_prevented_by_state_machine(tmp_path):
    """Approved executions cannot be queued a second time after success."""
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    execution = ApplicationExecution(
        job_key="job-1",
        company="Acme",
        title="Support Engineer",
        application_url="https://example.com/apply",
    )
    store.save(execution)
    machine.advance_to_ready(execution)
    machine.approve(execution)
    machine.queue(execution)
    machine.begin_apply(execution)
    machine.mark_submitted(execution, "reference: ABC-123")
    machine.verify_submission(execution, "reference: ABC-123")
    store.save(execution)

    # Second run must not re-queue a verified execution.
    assert machine.should_execute(execution) is False
    with pytest.raises(Exception):
        machine.queue(execution)
    assert store.by_job_key("job-1")[0].status == ExecutionStatus.SUBMISSION_VERIFIED


def test_restart_durability_preserves_unverified_state(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    execution = ApplicationExecution(
        job_key="job-1",
        company="Acme",
        title="Support Engineer",
        application_url="https://example.com/apply",
    )
    store.save(execution)
    machine.advance_to_ready(execution)
    machine.approve(execution)
    machine.queue(execution)
    machine.begin_apply(execution)
    machine.unverified_submission(execution, "submitted but confirmation not observed")
    store.save(execution)

    # Simulate a restart: a new store/machine over the same files.
    store2 = ExecutionStore(tmp_path)
    loaded = store2.by_job_key("job-1")[0]
    assert loaded.status == ExecutionStatus.SUBMISSION_UNVERIFIED
    assert loaded.execution.get("submission_unverified") is True
    # Unverified must not be silently re-executed or counted as verified.
    assert loaded.status != ExecutionStatus.SUBMISSION_VERIFIED


def test_runner_auto_discovers_and_records_verified(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    runner = ApplicationBatchRunner(store, machine)
    resume = tmp_path / "Subrat_Rout_Support_Engineer.pdf"
    resume.write_bytes(b"%PDF-1.4 test artifact")
    execution = ApplicationExecution(
        job_key="job-1",
        company="Acme",
        title="Support Engineer",
        application_url="https://boards.greenhouse.io/acme/jobs/1",
        pipeline={
            "profile": _profile(),
            "fields": [],
            "resume_path": str(resume),
        },
    )
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
        resume_path=ex.pipeline.get("resume_path"),
        steps=[Step(kind="open", target=ex.application_url)],
        fixture_pages={"open": _FORM_HTML, "confirm": _CONFIRMATION_HTML},
    )
    outcome = _run(runner.execute_batch(queued))
    assert outcome.submitted == 1
    assert outcome.verified == 1
    assert store.by_job_key("job-1")[0].status == ExecutionStatus.SUBMISSION_VERIFIED


def test_runner_marks_unverified_submission_state(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    runner = ApplicationBatchRunner(store, machine)
    execution = ApplicationExecution(
        job_key="job-1",
        company="Acme",
        title="Support Engineer",
        application_url="https://boards.greenhouse.io/acme/jobs/1",
        pipeline={"profile": _profile(), "fields": []},
    )
    store.save(execution)
    machine.advance_to_ready(execution)
    store.save(execution)
    approved = runner.approve_batch([execution])
    queued = runner.queue_batch(approved)

    form = '<label for="first">First name</label><input id="first" name="first_name" required>'

    runner.plan_builder = lambda ex: ApplicationPlan(
        execution_id=ex.execution_id,
        url=ex.application_url,
        profile=ex.pipeline.get("profile", {}),
        fields=ex.pipeline.get("fields", []),
        steps=[Step(kind="open", target=ex.application_url)],
        fixture_pages={"open": form, "after": "<html><body>still the form</body></html>"},
    )
    outcome = _run(runner.execute_batch(queued))
    assert outcome.submitted == 1
    assert outcome.unverified == 1
    assert outcome.verified == 0
    assert store.by_job_key("job-1")[0].status == ExecutionStatus.SUBMISSION_UNVERIFIED


def test_runner_needs_review_when_field_unresolved(tmp_path):
    store = ExecutionStore(tmp_path)
    machine = ApplicationExecutionStateMachine(store)
    runner = ApplicationBatchRunner(store, machine)
    execution = ApplicationExecution(
        job_key="job-1",
        company="Acme",
        title="Support Engineer",
        application_url="https://boards.greenhouse.io/acme/jobs/1",
        pipeline={"profile": _profile(), "fields": []},
    )
    store.save(execution)
    machine.advance_to_ready(execution)
    store.save(execution)
    approved = runner.approve_batch([execution])
    queued = runner.queue_batch(approved)

    form = (
        '<label for="first">First name</label><input id="first" name="first_name" required>'
        '<label for="sc">Do you hold a security clearance?</label>'
        '<input id="sc" name="clearance" type="text" required>'
    )
    runner.plan_builder = lambda ex: ApplicationPlan(
        execution_id=ex.execution_id,
        url=ex.application_url,
        profile=ex.pipeline.get("profile", {}),
        fields=ex.pipeline.get("fields", []),
        steps=[Step(kind="open", target=ex.application_url)],
        fixture_pages={"open": form, "confirm": _CONFIRMATION_HTML},
    )
    outcome = _run(runner.execute_batch(queued))
    assert outcome.submitted == 0
    assert outcome.needs_review == 1
    execution = store.by_job_key("job-1")[0]
    assert execution.status == ExecutionStatus.NEEDS_REVIEW
    assert execution.execution.get("review_fields")