from career_os.agents.jd_intelligence_agent import JDIntelligenceAgent


def test_jd_intelligence_agent_loads_skill_and_preserves_source() -> None:
    text = """Senior Product Support Analyst

Responsibilities
- Troubleshoot customer issues
- Analyze SQL queries and REST APIs

Requirements
- 2+ years of technical support experience
- SQL and Python

Preferred Qualifications
- Power BI experience

Location: Hyderabad
Work model: Hybrid
Salary: INR 8-12 LPA
"""

    agent = JDIntelligenceAgent()
    result = agent.analyze(text)

    assert agent.skill_name == "jd-intelligence"
    assert "Analyze SQL queries" in result.responsibilities
    assert "2+ years of technical support experience" in result.must_have_requirements
    assert "Power BI experience" in result.preferred_requirements
    assert "sql" in result.skills
    assert "python" in result.skills
    assert result.location == "Hyderabad"
    assert result.work_model == "hybrid"
    assert result.compensation == "INR 8-12 LPA"
    assert result.source_text == text.strip()


def test_jd_intelligence_does_not_invent_missing_fields() -> None:
    result = JDIntelligenceAgent().analyze("Responsibilities\n- Build reports")

    assert result.location is None
    assert result.compensation is None
    assert "Compensation not explicitly stated" in result.ambiguities
