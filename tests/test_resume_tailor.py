from career_os.agents.resume_tailor import ResumeTailor
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceLedger, EvidenceSource, SupportStatus
from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeBullet, ResumeProfile


def _ledger() -> EvidenceLedger:
    source = EvidenceSource("resume-1", "resume", "Master resume")
    return EvidenceLedger().add(
        EvidenceClaim(
            claim_id="c1",
            claim="Used SQL for troubleshooting and data validation",
            kind=EvidenceKind.VERIFIED,
            support=SupportStatus.SUPPORTED,
            confidence=1.0,
            source=source,
        )
    )


def test_resume_tailor_prioritizes_evidence_backed_jd_relevant_bullets() -> None:
    resume = ResumeProfile(
        summary="Technical support professional.",
        bullets=(
            ResumeBullet("Managed customer communication", ("c1",)),
            ResumeBullet("Used SQL for troubleshooting and data validation", ("c1",)),
        ),
    )
    jd = JDAnalysis(source_text="x", must_have_requirements=["SQL troubleshooting"], skills=["SQL"])

    result = ResumeTailor().tailor(resume, jd, _ledger())

    assert result.bullets[0].text.startswith("Used SQL")
    assert "sql" in result.matched_keywords
    assert result.bullets[0].evidence_claim_ids == ("c1",)


def test_resume_tailor_omits_unsupported_claims() -> None:
    resume = ResumeProfile(
        summary="Technical support professional.",
        bullets=(ResumeBullet("Python automation expert", ("unknown",)),),
    )
    jd = JDAnalysis(source_text="x", skills=["Python"])

    result = ResumeTailor().tailor(resume, jd, _ledger())

    assert result.bullets == ()
    assert result.omitted_claim_ids == ("c1",)


def test_resume_tailor_preserves_summary_and_does_not_invent_content() -> None:
    resume = ResumeProfile(summary="Original factual summary.", bullets=())
    jd = JDAnalysis(source_text="x", must_have_requirements=["Python"])

    result = ResumeTailor().tailor(resume, jd, _ledger())

    assert result.summary == "Original factual summary."
    assert result.bullets == ()
    assert "python" not in result.matched_keywords
