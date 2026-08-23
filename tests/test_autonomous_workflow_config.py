from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "career-os-autonomous.yml"
).read_text()


def test_autonomous_workflow_uses_supported_workspace_profile_safely():
    assert 'safety-strategy: drop-sudo' in WORKFLOW
    assert 'permission-profile: ":workspace"' in WORKFLOW
    assert "permission-profile: workspace-write" not in WORKFLOW
    assert "--full-auto" not in WORKFLOW
    assert "--skip-git-repo-check" not in WORKFLOW
    assert "danger-full-access" not in WORKFLOW
    assert "sandbox:" not in WORKFLOW
    assert "--sandbox" not in WORKFLOW


def test_autonomous_workflow_preserves_external_merge_handoff():
    assert "pull-requests: write" in WORKFLOW
    assert "issues: write" in WORKFLOW
    assert "NEVER merge a PR" in WORKFLOW
    assert "READY_TO_MERGE" in WORKFLOW
    assert "exact PR number, exact head SHA, and CI run URL" in WORKFLOW
    assert "HUMAN_REQUIRED" in WORKFLOW
    assert "workflow_run" in WORKFLOW
    assert "schedule:" in WORKFLOW
