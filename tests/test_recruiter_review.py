from career_os.audit.ats import audit_resume
from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeBullet, TailoredResume
from career_os.review.recruiter import review_candidate


def _resume(*, python: bool = True, linked: bool = True) -> TailoredResume:
    text = "Built data workflows with SQL and REST APIs."
    if python:
        text += " Used Python for automation."
    return TailoredResume(
        summary="Technical support analyst with automation experience.",
        bullets=(
            ResumeBullet(text, ("claim-1",) if linked else ()),
        ),
        matched_keywords=("SQL", "REST API"),
    )


def _jd() -> JDAnalysis:
    return JDAnalysis(
        source_text="Python required; REST API preferred.",
        must_have_requirements=["Python"],
        preferred_requirements=["REST API"],
        skills=["SQL"],
    )


def test_shortlists_when_required_evidence_is_present():
    resume = _resume()
    review = review_candidate(resume, _jd(), audit_resume(resume, _jd()))

    assert review.recommendation == "shortlist"
    assert review.confidence == "medium"
    assert not any(f.severity == "critical" for f in review.findings)
    assert review.shortlist_reasons


def test_missing_required_skill_is_a_material_gap():
    resume = _resume(python=False)
    review = review_candidate(resume, _jd(), audit_resume(resume, _jd()))

    assert review.recommendation == "review"
    finding = next(f for f in review.findings if f.category == "qualification-gap")
    assert finding.severity == "critical"
    assert finding.evidence == ("Python",)


def test_unlinked_bullet_is_a_credibility_risk():
    resume = _resume(linked=False)
    review = review_candidate(resume, _jd())

    finding = next(f for f in review.findings if f.category == "credibility")
    assert finding.severity == "high"
    assert finding.recommendation


def test_review_does_not_infer_unstated_experience():
    resume = _resume(python=False)
    review = review_candidate(resume, _jd())

    assert "Python" in review.findings[0].evidence
    assert all("adjacent" not in f.message.casefold() for f in review.findings)
