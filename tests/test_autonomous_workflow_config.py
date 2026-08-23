from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "career-os-autonomous.yml"
).read_text()


def test_autonomous_workflow_uses_pinned_official_gemini_action_safely():
    assert "google-github-actions/run-gemini-cli@f77273f4c914e4bf38440cf36a0369cb64a37489" in WORKFLOW
    assert "gemini_api_key: ${{ secrets.GEMINI_API_KEY }}" in WORKFLOW
    assert 'gemini_cli_version: "0.1.22"' in WORKFLOW
    assert 'GEMINI_CLI_TRUST_WORKSPACE: "true"' in WORKFLOW
    assert 'persist-credentials: false' in WORKFLOW
    assert "danger-full-access" not in WORKFLOW
    assert "--full-auto" not in WORKFLOW
    assert "--sandbox" not in WORKFLOW
    assert "GEMINI_DEBUG" not in WORKFLOW


def test_autonomous_workflow_preserves_external_merge_handoff():
    assert "pull-requests: write" in WORKFLOW
    assert "issues: write" in WORKFLOW
    assert "NEVER merge a PR" in WORKFLOW
    assert "READY_TO_MERGE" in WORKFLOW
    assert "exact PR number, exact head SHA, and CI run URL" in WORKFLOW
    assert "HUMAN_REQUIRED" in WORKFLOW
    assert "workflow_run" in WORKFLOW
    assert "schedule:" in WORKFLOW


def test_autonomous_workflow_preserves_research_first_sequence():
    research = WORKFLOW.index("1. Research relevant")
    implement = WORKFLOW.index("3. Implement")
    tests = WORKFLOW.index("4. Add/update deterministic")
    pr = WORKFLOW.index("6. Create/update a PR")
    verify = WORKFLOW.index("7. Dispatch the repository CI")
    handoff = WORKFLOW.index("READY_TO_MERGE")
    assert research < implement < tests < pr < verify < handoff
