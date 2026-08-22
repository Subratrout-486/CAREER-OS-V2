from career_os.audit import audit_resume
from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeBullet, TailoredResume


def test_ats_audit_matches_requirements_and_reports_gaps():
    resume = TailoredResume(
        summary="Technical support analyst with SQL and REST API experience.",
        bullets=(ResumeBullet("Troubleshot SQL incidents and documented root causes.", ("c1",)),),
    )
    jd = JDAnalysis(
        source_text="Support role",
        must_have_requirements=["SQL", "Python"],
        preferred_requirements=["REST API"],
        skills=["ServiceNow"],
    )

    audit = audit_resume(resume, jd)

    assert "SQL" in audit.matched_requirements
    assert "Python" in audit.missing_requirements
    assert "ServiceNow" in audit.missing_requirements
    assert audit.keyword_coverage == 0.25
    assert any(f.severity == "error" and f.category == "qualification-gap" for f in audit.findings)
    assert not audit.passed


def test_ats_audit_normalizes_common_skill_aliases():
    resume = TailoredResume(
        summary="Analyst using PowerBI and RESTful APIs.",
        bullets=(ResumeBullet("Validated reports and API integrations.", ("c1",)),),
    )
    jd = JDAnalysis(
        source_text="Analytics role",
        skills=["Power BI", "REST API"],
    )

    audit = audit_resume(resume, jd)

    assert audit.keyword_coverage == 1.0
    assert audit.missing_requirements == ()


def test_ats_audit_flags_missing_provenance_without_failing_qualification_gate():
    resume = TailoredResume(
        summary="Analyst",
        bullets=(ResumeBullet("Validated reporting outputs."),),
    )
    audit = audit_resume(resume, JDAnalysis(source_text="", skills=[]))

    assert audit.passed
    assert any(f.category == "provenance" and f.severity == "warning" for f in audit.findings)
