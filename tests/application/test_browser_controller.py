import json
from pathlib import Path
import pytest
import asyncio

from career_os.application.browser_runner import ApplicationForm, FormField, FieldMapping
from career_os.application.browser_controller import (
    BrowserAutomationController,
    ControllerStatus,
    BrowserAutomationState
)

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

    # Verify persistence
    loaded = BrowserAutomationController(state_path, runner=dummy_runner)
    assert loaded.state.status == ControllerStatus.INSPECTED

def test_controller_prepare(tmp_path: Path, dummy_runner):
    state_path = tmp_path / "controller.json"
    controller = BrowserAutomationController(state_path, runner=dummy_runner)
    controller.start("https://example.com/apply")

    # Mocking that inspect already ran
    controller.state.status = ControllerStatus.INSPECTED
    controller.state.form = {
        "url": "https://example.com/apply",
        "fields": [{"key": "first", "label": "First Name", "input_type": "text", "required": True, "options": []}]
    }

    profile = {"first_name": "Alice"}
    state = controller.step_prepare(profile)
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

def test_controller_fill(tmp_path: Path, dummy_runner):
    state_path = tmp_path / "controller.json"
    controller = BrowserAutomationController(state_path, runner=dummy_runner)
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
    assert state.fill_result is not None
    assert state.fill_result["filled"] == ["first"]

def test_execution_limit(tmp_path: Path, dummy_runner):
    state_path = tmp_path / "controller.json"
    controller = BrowserAutomationController(state_path, runner=dummy_runner, max_steps=1)
    controller.start("https://example.com/apply")

    asyncio.run(controller.step_inspect())
    assert controller.state.status == ControllerStatus.INSPECTED

    # Next step should trigger limit
    controller.step_prepare({"first_name": "Alice"})
    assert controller.state.status == ControllerStatus.LIMIT_EXCEEDED
    assert controller.state.error == "Execution limit exceeded"
