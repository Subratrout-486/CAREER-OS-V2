from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "career-os-autonomous.yml").read_text()


def test_autonomous_workflow_is_provider_free():
    assert "run-gemini-cli" not in WORKFLOW
    assert "codex-action" not in WORKFLOW
    assert "GEMINI_API_KEY" not in WORKFLOW
    assert "OPENAI_API_KEY" not in WORKFLOW
    assert "career_os_automation.py" in WORKFLOW
    assert "config/public_ats_sources.json" in WORKFLOW
    assert "candidate/source_of_truth.json" in WORKFLOW


def test_autonomous_workflow_runs_deterministic_verification_first():
    install = WORKFLOW.index("Install Career OS")
    tests = WORKFLOW.index("Run deterministic test suite")
    automation = WORKFLOW.index("Run provider-free Career OS automation")
    summary = WORKFLOW.index("Publish automation summary")
    assert install < tests < automation < summary


def test_autonomous_workflow_has_minimum_permissions_and_no_agent_shell_escape():
    assert "contents: read" in WORKFLOW
    assert "contents: write" not in WORKFLOW
    assert "pull-requests: write" not in WORKFLOW
    assert "issues: write" not in WORKFLOW
    assert "persist-credentials: false" in WORKFLOW
    assert "danger-full-access" not in WORKFLOW
    assert "--full-auto" not in WORKFLOW
    assert "--sandbox" not in WORKFLOW


def test_autonomous_workflow_is_scheduled_and_auditable():
    assert "schedule:" in WORKFLOW
    assert "workflow_dispatch:" in WORKFLOW
    assert "actions/upload-artifact@v4" in WORKFLOW
    assert "career-os-automation-report" in WORKFLOW
    assert "Application submission: **disabled**" in WORKFLOW
