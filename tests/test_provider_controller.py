from pathlib import Path

import pytest

from career_os.autonomy.provider_controller import (
    ControllerStatus,
    ProviderController,
    ProviderFailure,
    ProviderFailureKind,
    classify_provider_failure,
)


def test_failure_classifier_handles_quota_rate_limit_and_unknown():
    assert classify_provider_failure("You exceeded your current quota") is ProviderFailureKind.QUOTA
    assert classify_provider_failure("HTTP 429 rate limit") is ProviderFailureKind.RATE_LIMIT
    assert classify_provider_failure("unexpected parser error") is ProviderFailureKind.UNKNOWN


def test_controller_falls_back_without_losing_department_state(tmp_path: Path):
    state_path = tmp_path / "controller.json"
    controller = ProviderController(state_path, ["gemini", "codex"])
    controller.start(["research", "implementation"])

    assert controller.choose_provider() == "gemini"
    assert controller.record_provider_failure(
        ProviderFailure("gemini", ProviderFailureKind.QUOTA, "quota exhausted")
    ) == "codex"

    restored = ProviderController(state_path, ["gemini", "codex"])
    assert restored.state is not None
    assert restored.state.current_department == "research"
    assert restored.state.department_state is not None
    assert restored.state.department_state.provider_failures == {"gemini": ["quota"]}
    assert restored.state.department_state.provider == "codex"


def test_controller_emits_provider_blocked_after_all_authorized_providers_fail(tmp_path: Path):
    controller = ProviderController(tmp_path / "controller.json", ["gemini", "codex"])
    controller.start(["research"])
    assert controller.choose_provider() == "gemini"
    controller.record_provider_failure(ProviderFailure("gemini", ProviderFailureKind.QUOTA, "quota"))
    assert controller.record_provider_failure(
        ProviderFailure("codex", ProviderFailureKind.OUTAGE, "provider outage")
    ) is None

    handoff = controller.provider_blocked_handoff()
    assert handoff is not None
    assert handoff.status == "provider_blocked"
    assert handoff.department == "research"
    assert handoff.attempted_providers == ("gemini", "codex")
    assert "Authorize another provider" in handoff.next_action


def test_department_cannot_advance_before_ready_to_merge(tmp_path: Path):
    controller = ProviderController(tmp_path / "controller.json", ["gemini"])
    controller.start(["research", "implementation"])
    controller.choose_provider()
    with pytest.raises(ValueError, match="ready to merge"):
        controller.advance_department()

    controller.mark_ready_to_merge()
    next_department = controller.advance_department()
    assert next_department is not None
    assert next_department.department == "implementation"
