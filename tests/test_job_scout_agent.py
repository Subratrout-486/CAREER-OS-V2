from pathlib import Path

from career_os.agents.job_scout_agent import JobScoutAgent
from career_os.models.job import JobStatus


ROOT = Path(__file__).resolve().parents[1]


def test_job_scout_agent_loads_its_skill_and_executes_deterministic_logic() -> None:
    agent = JobScoutAgent(skills_root=ROOT / "skills")

    assert agent.context.skill.name == "job-scout"
    assert "Never invent" in agent.instructions

    first = agent.build_record(
        company="Acme",
        title="Support Engineer",
        location="Hyderabad",
        source_url="https://jobs.greenhouse.io/acme/jobs/123",
        source="Greenhouse",
        description="Support products and troubleshoot customer issues.",
    )
    second = agent.build_record(
        company="Acme",
        title="Support Engineer",
        location="Hyderabad",
        source_url="https://jobs.greenhouse.io/acme/jobs/123",
        source="Greenhouse",
        description="Support products and troubleshoot customer issues.",
    )

    records = agent.deduplicate([first, second])

    assert records[0].status is JobStatus.NEW
    assert records[1].status is JobStatus.DUPLICATE
    assert records[1].duplicate_of == records[0].job_id
