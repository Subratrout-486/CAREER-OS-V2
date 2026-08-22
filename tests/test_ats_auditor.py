from career_os.agents.ats_auditor import ATSAuditor
from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeBullet, ResumeProfile


def test_ats_auditor_reports_missing_keywords() -> None:
    resume = ResumeProfile("Support analyst.", (ResumeBullet("Used SQL for troubleshooting."),))
    jd = JDAnalysis(source_text="x", must_have_requirements=["SQL", "Python"], skills=["SQL", "Python"])

    result = ATSAuditor().audit(resume, jd)

    assert "sql" in result.matched_keywords
    assert "python" in result.missing_keywords
    assert any(f.code == "missing_keywords" for f in result.findings)


def test_ats_auditor_flags_empty_experience() -> None:
    result = ATSAuditor().audit(ResumeProfile("Summary", ()))

    assert any(f.code == "missing_experience" for f in result.findings)
    assert result.score < 100


def test_ats_auditor_flags_long_bullets() -> None:
    bullet = ResumeBullet("word " * 46)
    result = ATSAuditor().audit(ResumeProfile("Summary", (bullet,)))

    assert any(f.code == "long_bullet" for f in result.findings)
