from pathlib import Path


ROOT = Path(__file__).parents[1]
CURATED = {
    "research-first-planning",
    "systematic-debugging",
    "test-driven-development",
    "secure-pr-handoff",
}


def test_curated_skill_pack_is_small_and_local():
    skills_root = ROOT / "skills"
    discovered = {
        path.parent.name
        for path in skills_root.glob("*/SKILL.md")
        if not path.parent.name.startswith(".")
    }
    assert CURATED <= discovered
    assert len(CURATED) == 4
    assert not (ROOT / "skills_index.json").exists()
    assert not (ROOT / "plugins").exists()


def test_curated_skills_have_no_executable_payloads():
    for name in CURATED:
        skill_dir = ROOT / "skills" / name
        assert sorted(p.name for p in skill_dir.iterdir()) == ["SKILL.md"]


def test_autonomous_prompt_wires_curated_skills_and_keeps_gates():
    prompt = (ROOT / ".career-os" / "AUTONOMOUS_AGENT_PROMPT.md").read_text(encoding="utf-8")
    for name in CURATED:
        assert name in prompt
    assert "do not install or execute external skill catalogs" in prompt
    assert "NEVER merge a PR" in prompt
    assert "exact PR number, exact head SHA, and CI run URL" in prompt
    assert "Do not create or purchase credentials" in prompt
    assert "preserve the department state" in prompt


def test_curated_skill_pack_documents_exclusions_and_acceptance_criteria():
    manifest = (ROOT / ".career-os" / "CURATED_SKILLS.md").read_text(encoding="utf-8")
    for name in CURATED:
        assert f"`{name}`" in manifest
    assert "full external catalog" in manifest
    assert "No catalog code" in manifest
    assert "No test may require a provider credential" in manifest
