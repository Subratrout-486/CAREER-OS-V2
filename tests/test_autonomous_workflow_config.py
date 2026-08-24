from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "career-os-autonomous.yml").read_text()
PROMPT = (ROOT / ".career-os" / "AUTONOMOUS_AGENT_PROMPT.md").read_text()


def test_autonomous_workflow_is_provider_free():
    assert "google-github-actions/run-gemini-cli" not in WORKFLOW
    assert "openai/codex-action" not in WORKFLOW
    assert "GEMINI_API_KEY" not in WORKFLOW
    assert "OPENAI_API_KEY" not in WORKFLOW
    assert "career_os_provider_controller.py" not in WORKFLOW
    assert "provider-free smoke cycle (diagnostic only)" in WORKFLOW
    assert "python scripts/native_job_smoke_test.py" in WORKFLOW
    assert "persist-credentials: false" in WORKFLOW
    assert "danger-full-access" not in WORKFLOW
    assert "--full-auto" not in WORKFLOW
    assert "--sandbox" not in WORKFLOW


def test_autonomous_workflow_preserves_safe_handoff_and_verification_contract():
    assert "contents: read" in WORKFLOW
    assert "actions: read" in WORKFLOW
    assert "schedule:" in WORKFLOW
    assert "workflow_dispatch:" in WORKFLOW
    assert "repository_dispatch:" in WORKFLOW
    assert "NEVER merge a PR" in PROMPT
    assert "exact PR number, exact head SHA, and CI run URL" in PROMPT
    assert "HUMAN_REQUIRED" in PROMPT
    assert "PROVIDER_BLOCKED" in PROMPT


def test_workflow_run_checks_out_the_completed_ci_head_sha():
    exact_head_sha = "github.event_name == 'workflow_run' && github.event.workflow_run.head_sha || github.sha"
    assert exact_head_sha in WORKFLOW
    assert "ref: ${{ github.event_name == 'workflow_run' && github.event.workflow_run.head_sha || github.sha }}" in WORKFLOW
    assert "EXPECTED_SHA: ${{ github.event_name == 'workflow_run' && github.event.workflow_run.head_sha || github.sha }}" in WORKFLOW
    assert 'github.sha }}"' not in WORKFLOW.split("- name: Check out exact triggering commit", 1)[1].split("- name: Set up Python", 1)[0]


def test_autonomous_workflow_preserves_research_first_sequence():
    research = PROMPT.index("1. Research relevant")
    implement = PROMPT.index("3. Implement")
    tests = PROMPT.index("4. Add or update deterministic")
    pr = PROMPT.index("6. Create or update a PR")
    verify = PROMPT.index("7. Dispatch the repository CI")
    handoff = PROMPT.index("READY_TO_MERGE")
    assert research < implement < tests < pr < verify < handoff


def test_native_smoke_publishes_result_without_submission():
    assert "native-smoke-result.json" in WORKFLOW
    assert "actions/upload-artifact@v4" in WORKFLOW
    assert "submit" not in WORKFLOW.lower()
