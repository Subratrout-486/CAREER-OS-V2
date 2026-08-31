"""Durable autonomous execution loop for Career OS.

The loop is intentionally provider-neutral. A department executor performs one
small unit of work and returns a structured outcome. The loop persists after
every unit so a runner can be killed and restarted without losing progress.
Human approval is a first-class terminal state for actions such as submitting
an application; the loop never treats a blocked action as success.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Callable, Iterable


@dataclass(frozen=True)
class WorkOutcome:
    status: str  # completed | skipped | blocked | failed
    message: str = ""
    artifact: dict[str, object] = field(default_factory=dict)
    retryable: bool = False
    human_required: bool = False


@dataclass
class LoopState:
    run_id: str
    departments: list[str]
    completed: list[str] = field(default_factory=list)
    current: str | None = None
    status: str = "ready"  # ready | running | completed | blocked | failed
    iterations: int = 0
    failures: int = 0
    last_error: str | None = None
    artifacts: dict[str, dict[str, object]] = field(default_factory=dict)
    updated_at: str | None = None


class AutonomousLoop:
    """Run departments in order, checkpointing after every decision."""

    def __init__(self, state_path: Path, departments: Iterable[str]):
        self.state_path = state_path
        self.departments = list(dict.fromkeys(departments))
        if not self.departments:
            raise ValueError("at least one department is required")
        self.state = self._load()

    def run(
        self,
        run_id: str,
        executor: Callable[[str, LoopState], WorkOutcome],
        *,
        max_iterations: int = 100,
    ) -> LoopState:
        if self.state is None:
            self.state = LoopState(run_id=run_id, departments=self.departments)
        elif self.state.run_id != run_id:
            raise ValueError("state belongs to a different run")
        elif self.state.departments != self.departments:
            raise ValueError("department list cannot change for an existing run")

        if self.state.status == "completed":
            return self.state

        self.state.status = "running"
        self._save()

        while len(self.state.completed) < len(self.departments):
            if self.state.iterations >= max_iterations:
                self.state.status = "failed"
                self.state.last_error = "maximum loop iterations reached"
                self._save()
                break

            department = next(name for name in self.departments if name not in self.state.completed)
            self.state.current = department
            self.state.iterations += 1
            self._save()

            try:
                outcome = executor(department, self.state)
            except Exception as exc:  # noqa: BLE001 - boundary must checkpoint unexpected failures
                outcome = WorkOutcome(status="failed", message=str(exc), retryable=False)

            if outcome.status in {"completed", "skipped"}:
                if department not in self.state.completed:
                    self.state.completed.append(department)
                self.state.artifacts[department] = outcome.artifact
                self.state.current = None
                self.state.last_error = None
                self._save()
                continue

            if outcome.human_required or outcome.status == "blocked":
                self.state.status = "blocked"
                self.state.last_error = outcome.message or "human approval required"
                self.state.artifacts[department] = outcome.artifact
                self._save()
                break

            self.state.failures += 1
            self.state.last_error = outcome.message or "department failed"
            self.state.artifacts[department] = outcome.artifact
            self._save()
            if not outcome.retryable:
                self.state.status = "failed"
                break

            # Retryable failures remain the current department. The runner may
            # invoke this loop again, or the next scheduled cycle can resume it.
            self.state.status = "ready"
            self._save()
            break

        if len(self.state.completed) == len(self.departments):
            self.state.status = "completed"
            self.state.current = None
            self._save()
        return self.state

    def _load(self) -> LoopState | None:
        if not self.state_path.exists():
            return None
        return LoopState(**json.loads(self.state_path.read_text(encoding="utf-8")))

    def _save(self) -> None:
        if self.state is None:
            return
        self.state.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(self.state), indent=2, sort_keys=True) + "\n"
        with tempfile.NamedTemporaryFile("w", dir=self.state_path.parent, delete=False, encoding="utf-8") as handle:
            handle.write(payload)
            temporary = handle.name
        Path(temporary).replace(self.state_path)
