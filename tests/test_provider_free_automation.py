import json
from pathlib import Path

from scripts.career_os_automation import run


ROOT = Path(__file__).resolve().parents[1]


def test_provider_free_runner_completes_without_sources(tmp_path: Path):
    config = tmp_path / "sources.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "sources": [],
                "filters": {
                    "title_keywords": [],
                    "exclude_title_keywords": [],
                    "locations": [],
                    "max_jobs_per_source": 10,
                    "max_jobs_per_run": 10,
                    "min_description_chars": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "report.json"
    report = run(config, ROOT / "candidate/source_of_truth.json", output)

    assert report["status"] == "completed"
    assert report["jobs_discovered"] == 0
    assert report["jobs_evaluated"] == 0
    assert report["safety"]["llm_provider_required"] is False
    assert report["safety"]["credentials_required"] is False
    assert report["safety"]["application_submission"] == "disabled"
    assert output.exists()


def test_provider_free_runner_never_requires_gemini_or_codex():
    source = (ROOT / "scripts/career_os_automation.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/career-os-autonomous.yml").read_text(encoding="utf-8")

    assert "GEMINI_API_KEY" not in source
    assert "OPENAI_API_KEY" not in source
    assert "run-gemini-cli" not in workflow
    assert "codex-action" not in workflow
    assert "GEMINI_API_KEY" not in workflow
    assert "OPENAI_API_KEY" not in workflow


def test_public_ats_config_is_safe_by_default():
    config = json.loads((ROOT / "config/public_ats_sources.json").read_text(encoding="utf-8"))
    assert config["sources"] == []
    assert config["filters"]["max_jobs_per_run"] > 0
    assert config["filters"]["min_description_chars"] >= 0
