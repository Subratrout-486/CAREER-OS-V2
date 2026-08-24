from pathlib import Path
from career_os.candidate_profile import load_candidate_source_of_truth

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "candidate" / "source_of_truth.json"


def test_master_baseline_contains_verified_roles_and_dates() -> None:
    profile = load_candidate_source_of_truth(SOURCE)
    experience = {(x["company"], x["title"], x["dates"]) for x in profile["experience"]}
    assert ("FactSet Systems", "Product Support Engineer", "Nov 2024 – Jan 2026") in experience
    assert ("IGT Solutions", "Technical Operations Analyst", "Dec 2023 – May 2024") in experience
    assert ("Concentrix (Comcast)", "Technical Support Representative", "Nov 2021 – Oct 2022") in experience


def test_master_baseline_keeps_aws_as_project_experience() -> None:
    profile = load_candidate_source_of_truth(SOURCE)
    assert profile["projects"][0]["evidence_level"] == "project"
    assert "must not be rewritten as FactSet employment work" in " ".join(profile["truth_and_tailoring_rules"])


def test_master_baseline_rejects_superseded_role_titles() -> None:
    profile = load_candidate_source_of_truth(SOURCE)
    titles = {x["title"] for x in profile["experience"]}
    assert "Research Analyst / Product Support Engineer" not in titles
    assert "Process Associate — Group Reservations / Event Operations" not in titles
