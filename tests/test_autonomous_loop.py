from pathlib import Path

from career_os.autonomy.loop import AutonomousLoop, WorkOutcome


def test_loop_checkpoints_each_department(tmp_path: Path) -> None:
    state_path = tmp_path / "loop.json"
    calls: list[str] = []

    def executor(department: str, state):
        calls.append(department)
        return WorkOutcome(status="completed", artifact={"ok": True})

    result = AutonomousLoop(state_path, ["discover", "analyze", "prepare"]).run("r1", executor)

    assert result.status == "completed"
    assert result.completed == ["discover", "analyze", "prepare"]
    assert calls == ["discover", "analyze", "prepare"]


def test_blocked_work_is_not_success(tmp_path: Path) -> None:
    state_path = tmp_path / "loop.json"

    def executor(department: str, state):
        return WorkOutcome(status="blocked", message="approval required", human_required=True)

    result = AutonomousLoop(state_path, ["submit"]).run("r2", executor)

    assert result.status == "blocked"
    assert result.completed == []
    assert result.current == "submit"


def test_retryable_failure_can_resume(tmp_path: Path) -> None:
    state_path = tmp_path / "loop.json"
    attempts = 0

    def executor(department: str, state):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return WorkOutcome(status="failed", message="temporary outage", retryable=True)
        return WorkOutcome(status="completed")

    first = AutonomousLoop(state_path, ["work"]).run("r3", executor)
    assert first.status == "ready"
    assert first.completed == []

    second = AutonomousLoop(state_path, ["work"]).run("r3", executor)
    assert second.status == "completed"
    assert second.completed == ["work"]
