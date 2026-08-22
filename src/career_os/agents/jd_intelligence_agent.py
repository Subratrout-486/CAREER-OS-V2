from __future__ import annotations

from pathlib import Path

from career_os.agents.jd_intelligence import JDIntelligence
from career_os.agents.skill_agent import SkillBackedAgent
from career_os.models.jd import JDAnalysis


class JDIntelligenceAgent(SkillBackedAgent):
    """Skill-backed JD Intelligence department."""

    skill_name = "jd-intelligence"

    def __init__(self, *, skills_root: Path | None = None) -> None:
        super().__init__(skills_root=skills_root)
        self.analyzer = JDIntelligence()

    def analyze(self, text: str) -> JDAnalysis:
        return self.execute(lambda: self.analyzer.analyze(text))
