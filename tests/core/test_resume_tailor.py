from career_os.core.resume_tailor import ResumeTailor
from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeBullet, ResumeProfile


def test_tailor_prioritizes_existing_evidence_only():
    resume = ResumeProfile(
        summary="Support analyst with SQL and ServiceNow exposure.",
        bullets=(
            ResumeBullet("Managed customer communication and coordination.", ("c1",)),
            ResumeBullet("Used SQL queries and ServiceNow for incident troubleshooting.", ("c2",)),
        ),
    )
    jd = JDAnalysis(source_text="test", skills=["SQL", "ServiceNow"], domain_terms=["incident troubleshooting"])

    result = ResumeTailor().tailor(jd, resume)

    assert result.bullets[0].evidence_claim_ids == ("c2",)
    assert "SQL" in result.matched_keywords
    assert "ServiceNow" in result.matched_keywords
    assert all("invent" not in note.casefold() for note in result.edit_trace)


def test_tailor_does_not_create_new_claims():
    resume = ResumeProfile(summary="Analyst", bullets=(ResumeBullet("Validated records.", ("c1",)),))
    jd = JDAnalysis(source_text="test", skills=["Python", "AWS"])

    result = ResumeTailor().tailor(jd, resume)

    assert result.matched_keywords == ()
    assert result.bullets == resume.bullets
