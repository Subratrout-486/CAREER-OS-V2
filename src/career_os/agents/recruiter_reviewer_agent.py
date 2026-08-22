from __future__ import annotations

from career_os.agents.recruiter_reviewer import RecruiterReviewer
from career_os.core.skills import SkillRegistry
from career_os.models.evidence import EvidenceLedger
from career_os.models.fit import FitScore
from career_os.models.jd import JDAnalysis
from career_os.models.resume import TailoredResume
from career_os.models.recruiter_review import RecruiterReview


class RecruiterReviewerAgent:
    """Skill-backed facade for recruiter-style review."""

    name = "recruiter_reviewer_agent"
    skill_name = "recruiter-review"

    def __init__(self, skill_root: str = "skills") -> None:
        self._registry = SkillRegistry(skill_root)
        self.skill = self._registry.load(self.skill_name)
        self._reviewer = RecruiterReviewer()

    def review(self, jd: JDAnalysis, resume: TailoredResume, fit: FitScore, evidence: EvidenceLedger) -> RecruiterReview:
        return self._reviewer.review(jd, resume, fit, evidence)
