from career_os.agents.recruiter_reviewer import RecruiterReviewer
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceLedger, EvidenceSource, SupportStatus
from career_os.models.fit import FitScore
from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeBullet, TailoredResume


def _evidence() -> EvidenceLedger:
    source = EvidenceSource("resume-1", "resume", "Master resume")
    return EvidenceLedger().add(
        EvidenceClaim(
            claim_id="c1",
            claim="Python and SQL support experience",
            kind=EvidenceKind.VERIFIED,
            support=SupportStatus.SUPPORTED,
            confidence=1.0,
            source=source,
        )
    )


def _resume() -> TailoredResume:
    return TailoredResume(
        summary="Technical support analyst with Python and SQL experience.",
        bullets=(ResumeBullet("Supported Python and SQL workflows.", ("c1",)),),
    )


def test_strong_fit_can_be_shortlisted_with_traceable_evidence() -> None:
    jd = JDAnalysis(source_text="x", must_have_requirements=["Python"], skills=["SQL"])
    fit = FitScore(100, 100, 100, 100, evidence_claim_ids=("c1",), recommendation="strong_fit")
    result = RecruiterReviewer().review(jd, _resume(), fit, _evidence())

    assert result.recommendation == "shortlist"
    assert result.evidence_claim_ids == ("c1",)
    assert result.risks == ()


def test_hard_gap_is_never_hidden() -> None:
    jd = JDAnalysis(source_text="x", must_have_requirements=["Oracle"])
    fit = FitScore(40, 0, 100, 100, hard_gaps=("Oracle",), recommendation="hard_gap")
    result = RecruiterReviewer().review(jd, _resume(), fit, _evidence())

    assert result.recommendation == "do_not_shortlist"
    assert "Missing hard requirement: Oracle" in result.objections


def test_unsupported_resume_claim_triggers_manual_review() -> None:
    jd = JDAnalysis(source_text="x", must_have_requirements=["Python"])
    resume = TailoredResume(summary="", bullets=(ResumeBullet("Python", ("unverified",)),))
    fit = FitScore(90, 100, 100, 100, recommendation="strong_fit")
    result = RecruiterReviewer().review(jd, resume, fit, _evidence())

    assert result.recommendation == "manual_review"
    assert result.risks
