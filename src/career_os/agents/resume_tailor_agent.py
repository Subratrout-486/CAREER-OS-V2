from __future__ import annotations

from career_os.agents.resume_tailor import ResumeTailor
from career_os.core.skills import SkillRegistry
from career_os.models.evidence import EvidenceLedger
from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeProfile, TailoredResume


class ResumeTailorAgent:
    """Skill-backed facade for the deterministic Resume Tailor."""

    name = "resume_tailor_agent"
    skill_name = "resume-tailoring"

    def __init__(self, skill_root: str = "skills") -> None:
        self._registry = SkillRegistry(skill_root)
        self.skill = self._registry.load(self.skill_name)
        self._tailor = ResumeTailor()

    def tailor(self, resume: ResumeProfile, jd: JDAnalysis, ledger: EvidenceLedger) -> TailoredResume:
        return self._tailor.tailor(resume, jd, ledger)
