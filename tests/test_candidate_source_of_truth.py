from pathlib import Path

import pytest

from career_os.candidate_profile import (
    CandidateSourceOfTruthError,
    load_candidate_source_of_truth,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate" / "source_of_truth.json"


def test_source_of_truth_loads_with_all_skill_categories() -> None:
    profile = load_candidate_source_of_truth(SOURCE)

    assert profile["candidate"]["name"] == "Subrat Rout"
    assert profile["projects"][0]["name"] == "AWS Infrastructure & Automation Labs"
    assert "LLM fundamentals" in profile["skills_and_tools"]["knowledge_and_professional_development"]
    assert "Prompt engineering" in profile["skills_and_tools"]["knowledge_and_professional_development"]
    assert "AI agents" in profile["skills_and_tools"]["knowledge_and_professional_development"]
    assert "Python" in profile["skills_and_tools"]["professional_experience"]
    assert "AWS EC2" in profile["skills_and_tools"]["project_experience"]


def test_source_of_truth_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(CandidateSourceOfTruthError, match="not found"):
        load_candidate_source_of_truth(tmp_path / "missing.json")


def test_source_of_truth_keeps_employment_and_projects_separate() -> None:
    profile = load_candidate_source_of_truth(SOURCE)

    assert all(item["evidence_level"] == "professional" for item in profile["experience"])
    assert profile["projects"][0]["evidence_level"] == "project"
    assert "must not be rewritten as FactSet employment work" in " ".join(profile["truth_and_tailoring_rules"])
