from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from career_os.application.browser_runner import BrowserApplicationRunner, FieldMapping, FormField, map_profile_fields


class ControllerStatus(str, Enum):
    READY = "READY"
    INSPECTED = "INSPECTED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    FILLED = "FILLED"
    FAILED = "FAILED"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"


@dataclass
class BrowserAutomationState:
    url: str
    status: ControllerStatus = ControllerStatus.READY
    form: dict[str, Any] | None = None
    mappings: list[dict[str, Any]] = field(default_factory=list)
    fill_result: dict[str, Any] | None = None
    step_count: int = 0
    max_steps: int = 10
    error: str | None = None


class BrowserAutomationController:
    """Durable controller for browser automation with execution limits and human checkpoints."""

    def __init__(self, state_path: Path, runner: BrowserApplicationRunner | None = None, max_steps: int = 10):
        self.state_path = state_path
        self.runner = runner or BrowserApplicationRunner()
        self.max_steps = max_steps
        self.state: BrowserAutomationState | None = self._load()

    def start(self, url: str) -> BrowserAutomationState:
        if self.state is not None and self.state.url != url:
            raise ValueError("Controller already started with a different URL")
        if self.state is None:
            self.state = BrowserAutomationState(url=url, max_steps=self.max_steps)
            self._save()
        return self.state

    def _check_limit(self) -> bool:
        if self.state is None:
            raise RuntimeError("Controller not started")
        if self.state.step_count >= self.state.max_steps:
            self.state.status = ControllerStatus.LIMIT_EXCEEDED
            self.state.error = "Execution limit exceeded"
            self._save()
            return False
        self.state.step_count += 1
        self._save()
        return True

    async def step_inspect(self) -> BrowserAutomationState:
        if self.state is None:
            raise RuntimeError("Controller not started")
        if self.state.status != ControllerStatus.READY:
            raise RuntimeError(f"Cannot inspect from status {self.state.status.value}")
        if not self._check_limit():
            return self.state

        try:
            form = await self.runner.inspect(self.state.url)
            self.state.form = {"url": form.url, "fields": [asdict(f) for f in form.fields]}
            self.state.status = ControllerStatus.INSPECTED
        except Exception as e:
            self.state.error = str(e)
            self.state.status = ControllerStatus.FAILED

        self._save()
        return self.state

    def step_prepare(self, profile: dict[str, Any]) -> BrowserAutomationState:
        if self.state is None:
            raise RuntimeError("Controller not started")
        if self.state.status != ControllerStatus.INSPECTED:
            raise RuntimeError(f"Cannot prepare mappings from status {self.state.status.value}")
        if not self._check_limit():
            return self.state

        fields = [FormField(**f) for f in self.state.form["fields"]]
        mappings = map_profile_fields(fields, profile)

        self.state.mappings = [
            {
                "field": asdict(m.field),
                "profile_key": m.profile_key,
                "value": m.value,
                "confidence": m.confidence
            } for m in mappings
        ]
        self.state.status = ControllerStatus.WAITING_APPROVAL
        self._save()
        return self.state

    def provide_approval(self, approved: bool, modifications: list[dict[str, Any]] | None = None) -> BrowserAutomationState:
        if self.state is None:
            raise RuntimeError("Controller not started")
        if self.state.status != ControllerStatus.WAITING_APPROVAL:
            raise RuntimeError(f"Not waiting for approval, current status is {self.state.status.value}")

        if not approved:
            self.state.status = ControllerStatus.FAILED
            self.state.error = "Human approval rejected"
        else:
            if modifications is not None:
                if not all(isinstance(item, dict) and isinstance(item.get("field"), dict) and item["field"].get("key") for item in modifications):
                    self.state.status = ControllerStatus.FAILED
                    self.state.error = "Invalid approval modifications"
                    self._save()
                    return self.state
                self.state.mappings = modifications
            self.state.status = ControllerStatus.APPROVED

        self._save()
        return self.state

    async def step_fill(self) -> BrowserAutomationState:
        if self.state is None:
            raise RuntimeError("Controller not started")
        if self.state.status != ControllerStatus.APPROVED:
            raise RuntimeError(f"Cannot fill from status {self.state.status.value}")
        if not self._check_limit():
            return self.state

        mappings = []
        for m in self.state.mappings:
            field_data = m["field"]
            mappings.append(FieldMapping(
                field=FormField(**field_data),
                profile_key=m.get("profile_key"),
                value=m.get("value"),
                confidence=m.get("confidence", 1.0)
            ))

        try:
            result = await self.runner.fill(self.state.url, mappings)
            self.state.fill_result = result
            self.state.status = ControllerStatus.FILLED
        except Exception as e:
            self.state.error = str(e)
            self.state.status = ControllerStatus.FAILED

        self._save()
        return self.state

    def _load(self) -> BrowserAutomationState | None:
        if not self.state_path.exists():
            return None
        raw = json.loads(self.state_path.read_text())
        if "status" in raw:
            raw["status"] = ControllerStatus(raw["status"])
        return BrowserAutomationState(**raw)

    def _save(self) -> None:
        if self.state is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state_dict = asdict(self.state)
        if isinstance(state_dict["status"], ControllerStatus):
            state_dict["status"] = state_dict["status"].value

        payload = json.dumps(state_dict, indent=2, sort_keys=True) + "\n"
        with tempfile.NamedTemporaryFile("w", dir=self.state_path.parent, delete=False) as handle:
            handle.write(payload)
            temp_name = handle.name
        Path(temp_name).replace(self.state_path)
