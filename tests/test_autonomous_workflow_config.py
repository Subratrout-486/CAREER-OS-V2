from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "career-os-autonomous.yml").read_text()
PROMPT = (ROOT / ".career-os" / "AUTONOMOUS_AGENT_PROMPT.md").read_text()


def test_autonomous_workflow_uses_supported_provider_adapters_safely():
    assert "google-github-actions/run-gemini-cli@f77273f4c914e4bf38440cf36a0369cb64a37489" in WORKFLOW
    assert "openai/codex-action@v1" in WORKFLOW
    assert "gemini_api_key: ${{ secrets.GEMINI_API_KEY }}" in WORKFLOW
    assert "openai-api-key: ${{ secrets.OPENAI_API_KEY }}" in WORKFLOW
    assert 'gemini_cli_version: "preview"' in WORKFLOW
    assert 'GEMINI_CLI_TRUST_WORKSPACE: "true"' in WORKFLOW
    assert '"sandbox": "docker"' in WORKFLOW
    assert 'permission-profile: ":workspace"' in WORKFLOW
    assert "safety-strategy: drop-sudo" in WORKFLOW
    assert 'persist-credentials: false' in WORKFLOW
    assert "danger-full-access" not in WORKFLOW
    assert "--full-auto" not in WORKFLOW
    assert "--sandbox" not in WORKFLOW


def test_autonomous_workflow_preserves_external_merge_handoff():
    assert "pull-requests: write" in WORKFLOW
    assert "issues: write" in WORKFLOW
    assert "NEVER merge a PR" in PROMPT
    assert "READY_TO_MERGE" in PROMPT
    assert "exact PR number, exact head SHA, and CI run URL" in PROMPT
    assert "HUMAN_REQUIRED" in PROMPT
    assert "PROVIDER_BLOCKED" in PROMPT
    assert "workflow_run" in WORKFLOW
    assert "schedule:" in WORKFLOW


def test_autonomous_workflow_preserves_research_first_sequence():
    research = PROMPT.index("1. Research relevant")
    implement = PROMPT.index("3. Implement")
    tests = PROMPT.index("4. Add or update deterministic")
    pr = PROMPT.index("6. Create or update a PR")
    verify = PROMPT.index("7. Dispatch the repository CI")
    handoff = PROMPT.index("READY_TO_MERGE")
    assert research < implement < tests < pr < verify < handoff


def test_provider_blocked_is_a_durable_handoff_not_infrastructure_failure():
    assert "Provider exhaustion is a durable handoff state" in WORKFLOW
    assert "exit 0" in WORKFLOW
    assert "Fail if selected provider failed without fallback" in WORKFLOW


def test_controller_runs_before_provider_actions():
    controller = WORKFLOW.index("Select first authorized provider")
    gemini = WORKFLOW.index("Run Career OS cycle with Gemini")
    fallback = WORKFLOW.index("Select fallback after Gemini failure")
    codex = WORKFLOW.index("Run fallback Career OS cycle with Codex")
    assert controller < gemini < fallback < codex
