from __future__ import annotations

from career_os.agents.ats_auditor import ATSAuditor
from career_os.core.skills import SkillRegistry
from career_os.models.ats import ATSAudit
from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeProfile


class ATSAuditorAgent:
    """Skill-backed facade for deterministic ATS auditing."""

    name = "ats_auditor_agent"
    skill_name = "ats-audit"

    def __init__(self, skill_root: str = "skills") -> None:
        self._registry = SkillRegistry(skill_root)
        self.skill = self._registry.load(self.skill_name)
        self._auditor = ATSAuditor()

    def audit(self, resume: ResumeProfile, jd: JDAnalysis | None = None) -> ATSAudit:
        return self._auditor.audit(resume, jd)
