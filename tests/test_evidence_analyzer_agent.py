from career_os.agents.evidence_analyzer_agent import EvidenceAnalyzerAgent


def test_skill_backed_evidence_agent_loads_and_validates():
    agent = EvidenceAnalyzerAgent()
    assert agent.skill.name == "evidence-analysis"
