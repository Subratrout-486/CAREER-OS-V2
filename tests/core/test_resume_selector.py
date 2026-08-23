from career_os.core.resume_selector import ResumeCandidate, ResumeSelector
from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeBullet, ResumeProfile


def test_selector_prefers_resume_with_stronger_jd_evidence():
    jd = JDAnalysis(source_text="test", skills=["SQL", "Power BI"], domain_terms=["analytics"])
    analytics = ResumeCandidate("analytics", ResumeProfile("Analytics professional", (ResumeBullet("SQL and Power BI analytics"),)))
    support = ResumeCandidate("support", ResumeProfile("Support professional", (ResumeBullet("Ticket troubleshooting"),)))
    result = ResumeSelector().select(jd, [support, analytics])
    assert result.name == "analytics"
    assert result.score > 0


def test_selector_does_not_invent_claims():
    jd = JDAnalysis(source_text="test", skills=["Python"])
    resume = ResumeCandidate("base", ResumeProfile("Support professional", (ResumeBullet("Ticket troubleshooting"),)))
    result = ResumeSelector().select(jd, [resume])
    assert result.name == "base"
    assert "python" in result.missing_terms
