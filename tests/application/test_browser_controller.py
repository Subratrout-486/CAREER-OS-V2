import asyncio
from pathlib import Path

import pytest

from career_os.application.browser_controller import BrowserAutomationController, ControllerStatus
from career_os.application.browser_runner import ApplicationForm, FieldMapping, FormField


class DummyRunner:
    async def inspect(self, url: str) -> ApplicationForm:
        return ApplicationForm(
            url=url,
            fields=[FormField(key="first", label="First Name", required=True)]
        )

    async def fill(self, url: str, mappings: list[FieldMapping]) -> dict:
        return {"url": url, "filled": ["first"], "skipped": [], "submitted": False}


@pytest.fixture
def dummy_runner():
    return DummyRunner()


def test_controller_initialization(tmp_path: Path):
    state_path = tmp_path / "controller.json"
    controller = BrowserAutomationController(state_path)
    state = controller.start("https://example.com/apply")
    assert state.url == "https://example.com/apply"
    assert state.status == ControllerStatus.READY


def test_controller_inspect(tmp_path: Path, dummy_runner):
    state_path = tmp_path / "controller.json"
    controller = BrowserAutomationController(state_path, runner=dummy_runner)
    controller.start("https://example.com/apply")

    state = asyncio.run(controller.step_inspect())
    assert state.status == ControllerStatus.INSPECTED
    assert state.form is not None
    assert state.form["fields"][0]["key"] == "first"
    assert state.step_count == 1

    loaded = BrowserAutomationController(state_path, runner=dummy_runner)
    assert loaded.state.status == ControllerStatus.INSPECTED


def test_controller_prepare(tmp_path: Path, dummy_runner):
    state_path = tmp_path / "controller.json"
    controller = BrowserAutomationController(state_path, runner=dummy_runner)
    controller.start("https://example.com/apply")
    controller.state.status = ControllerStatus.INSPECTED
    controller.state.form = {
        "url": "https://example.com/apply",
        "fields": [{"key": "first", "label": "First Name", "input_type": "text", "required": True, "options": []}]
    }

    state = controller.step_prepare({"first_name": "Alice"})
    assert state.status == ControllerStatus.WAITING_APPROVAL
    assert len(state.mappings) == 1
    assert state.mappings[0]["value"] == "Alice"
    assert state.mappings[0]["confidence"] == 1.0


def test_controller_approval(tmp_path: Path, dummy_runner):
    state_path = tmp_path / "controller.json"
    controller = BrowserAutomationController(state_path, runner=dummy_runner)
    controller.start("https://example.com/apply")
    controller.state.status = ControllerStatus.WAITING_APPROVAL

    state = controller.provide_approval(approved=True)
    assert state.status == ControllerStatus.APPROVED

    controller.state.status = ControllerStatus.WAITING_APPROVAL
    state = controller.provide_approval(approved=False)
    assert state.status == ControllerStatus.FAILED
    assert state.error == "Human approval rejected"


def test_invalid_approval_modification_fails_closed(tmp_path: Path, dummy_runner):
    state_path = tmp_path / "controller.json"
    controller = BrowserAutomationController(state_path, runner=dummy_runner)
    controller.start("https://example.com/apply")
    controller.state.status = ControllerStatus.WAITING_APPROVAL

    state = controller.provide_approval(approved=True, modifications=[{"profile_key": "first_name"}])

    assert state.status == ControllerStatus.FAILED
    assert state.error == "Invalid approval modifications"
    assert state.mappings == []


def test_invalid_lifecycle_call_does_not_consume_step_budget(tmp_path: Path, dummy_runner):
    state_path = tmp_path / "controller.json"
    controller = BrowserAutomationController(state_path, runner=dummy_runner, max_steps=1)
    controller.start("https://example.com/apply")

    with pytest.raises(RuntimeError, match="Cannot fill from status READY"):
        asyncio.run(controller.step_fill())

    assert controller.state.status == ControllerStatus.READY
    assert controller.state.step_count == 0


def test_duplicate_fill_does_not_consume_step_budget_or_change_terminal_state(tmp_path: Path, dummy_runner):
    state_path = tmp_path / "controller.json"
    controller = BrowserAutomationController(state_path, runner=dummy_runner, max_steps=2)
    controller.start("https://example.com/apply")
    controller.state.status = ControllerStatus.APPROVED
    controller.state.mappings = [{
        "field": {"key": "first", "label": "First Name", "input_type": "text", "required": True, "options": []},
        "profile_key": "first_name",
        "value": "Alice",
        "confidence": 1.0
    }]

    state = asyncio.run(controller.step_fill())
    assert state.status == ControllerStatus.FILLED
    assert state.step_count == 1

    with pytest.raises(RuntimeError, match="Cannot fill from status FILLED"):
        asyncio.run(controller.step_fill())

    assert controller.state.status == ControllerStatus.FILLED
    assert controller.state.step_count == 1


def test_execution_limit(tmp_path: Path, dummy_runner):
    state_path = tmp_path / "controller.json"
    controller = BrowserAutomationController(state_path, runner=dummy_runner, max_steps=1)
    controller.start("https://example.com/apply")

    asyncio.run(controller.step_inspect())
    assert controller.state.status == ControllerStatus.INSPECTED

    controller.step_prepare({"first_name": "Alice"})
    assert controller.state.status == ControllerStatus.LIMIT_EXCEEDED
    assert controller.state.error == "Execution limit exceeded"
