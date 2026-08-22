from __future__ import annotations

from career_os.agents.evidence_analyzer import EvidenceAnalyzer
from career_os.core.skills import SkillRegistry


class EvidenceAnalyzerAgent:
    """Skill-backed facade for evidence validation and provenance."""

    name = "evidence_analyzer_agent"
    skill_name = "evidence-analysis"

    def __init__(self, skill_root: str = "skills") -> None:
        self._registry = SkillRegistry(skill_root)
        self.skill = self._registry.get(self.skill_name)
        self._analyzer = EvidenceAnalyzer()

    def build_ledger(self, claims):
        return self._analyzer.build_ledger(claims)

    def material_gaps(self, ledger):
        return self._analyzer.material_gaps(ledger)
