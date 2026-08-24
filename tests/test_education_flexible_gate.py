from career_os.agents.fit_scorer import FitScorer
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceLedger, EvidenceSource, SupportStatus
from career_os.models.jd import JDAnalysis


def _ledger(*claims: str) -> EvidenceLedger:
    source = EvidenceSource("resume-1", "resume", "Master resume")
    ledger = EvidenceLedger()
    for index, text in enumerate(claims, start=1):
        ledger = ledger.add(
            EvidenceClaim(
                claim_id=f"c{index}",
                claim=text,
                kind=EvidenceKind.VERIFIED,
                support=SupportStatus.SUPPORTED,
                confidence=1.0,
                source=source,
            )
        )
    return ledger


def test_btech_requirement_does_not_create_hard_gap_for_bcom_candidate() -> None:
    jd = JDAnalysis(
        source_text="x",
        must_have_requirements=["B.Tech degree", "2 years of technical support"],
    )
    result = FitScorer().score(jd, _ledger("B.Com degree", "2 years of technical support"))

    assert result.hard_requirements == 100.0
    assert result.hard_gaps == ()
    assert result.education_gaps == ("B.Tech degree",)
    assert result.education_risk == "mismatch"
    assert result.recommendation != "hard_gap"


def test_education_only_mismatch_does_not_reduce_overall_fit() -> None:
    without_education = JDAnalysis(source_text="x", must_have_requirements=["Python"])
    with_education = JDAnalysis(source_text="x", must_have_requirements=["Python", "Bachelor's degree"])
    ledger = _ledger("Python")

    baseline = FitScorer().score(without_education, ledger)
    result = FitScorer().score(with_education, ledger)

    assert result.overall == baseline.overall
    assert result.education_gaps == ("Bachelor's degree",)
    assert result.education_risk == "mismatch"
    assert result.hard_gaps == ()


def test_non_education_hard_gap_still_blocks() -> None:
    jd = JDAnalysis(source_text="x", must_have_requirements=["B.Tech degree", "Oracle"])
    result = FitScorer().score(jd, _ledger("B.Com degree"))

    assert result.education_gaps == ("B.Tech degree",)
    assert result.hard_gaps == ("Oracle",)
    assert result.recommendation == "hard_gap"
