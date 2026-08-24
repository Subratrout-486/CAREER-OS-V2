from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "notion_resume_finalize",
    SCRIPTS / "notion_resume_finalize.py",
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_load_completed_result_rehydrates_checkpoint_without_rerun(tmp_path: Path) -> None:
    checkpoint = tmp_path / "run.json"
    checkpoint.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "status": "completed",
                "completed_stages": [
                    "job_intake",
                    "jd_intelligence",
                    "evidence_analysis",
                    "fit_scoring",
                    "resume_tailoring",
                    "ats_audit",
                    "recruiter_review",
                    "application_readiness",
                ],
                "artifacts": {
                    "job_intake": {"title": "Associate Technical Support Engineer"},
                    "fit_scoring": {"score": 82.0, "hard_gaps": []},
                    "resume_tailoring": {
                        "summary": "Support Engineer",
                        "bullets": [
                            {"text": "Incident management", "evidence_claim_ids": ["c1"]}
                        ],
                        "matched_keywords": ["support"],
                        "omitted_claim_ids": [],
                        "edit_trace": [],
                    },
                    "ats_audit": {"findings": []},
                    "application_readiness": {"ready": True, "findings": []},
                },
            }
        ),
        encoding="utf-8",
    )

    result = module.load_completed_result(checkpoint)

    assert result.job.title == "Associate Technical Support Engineer"
    assert result.tailored_resume.summary == "Support Engineer"
    assert result.tailored_resume.bullets[0].text == "Incident management"
    assert result.fit.score == 82.0
    assert result.application_ready is True


def test_load_completed_result_rejects_incomplete_checkpoint(tmp_path: Path) -> None:
    checkpoint = tmp_path / "run.json"
    checkpoint.write_text(
        json.dumps({"run_id": "run-1", "status": "running", "artifacts": {}}),
        encoding="utf-8",
    )

    try:
        module.load_completed_result(checkpoint)
    except RuntimeError as exc:
        assert "not completed" in str(exc)
    else:
        raise AssertionError("Expected incomplete checkpoint to be rejected")
