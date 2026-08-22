from pathlib import Path

import pytest

from career_os.core.skills import SkillError, SkillRegistry


EXPECTED_SKILLS = {
    "job-scout",
    "jd-intelligence",
    "evidence-analysis",
    "fit-scoring",
    "resume-tailoring",
    "ats-audit",
    "recruiter-review",
    "application-management",
    "interview-coach",
    "learning",
}


def test_all_career_departments_are_discoverable():
    registry = SkillRegistry(Path(__file__).parents[1] / "skills")

    skills = registry.discover()

    assert {skill.name for skill in skills} == EXPECTED_SKILLS
    assert all(skill.description for skill in skills)
    assert all(skill.instructions for skill in skills)


def test_skill_loading_is_progressive_and_targeted():
    registry = SkillRegistry(Path(__file__).parents[1] / "skills")

    skill = registry.get("job-scout")

    assert skill.path.name == "SKILL.md"
    assert "deduplicate" in skill.instructions
    assert "ghost jobs" in skill.instructions


def test_unknown_skill_is_rejected():
    registry = SkillRegistry(Path(__file__).parents[1] / "skills")

    with pytest.raises(SkillError, match="Unknown skill"):
        registry.get("does-not-exist")


def test_invalid_skill_metadata_is_rejected(tmp_path):
    skill_dir = tmp_path / "bad-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: different-name\ndescription: test\n---\n\nInstructions.\n",
        encoding="utf-8",
    )

    with pytest.raises(SkillError, match="directory and metadata must match"):
        SkillRegistry(tmp_path).discover()
