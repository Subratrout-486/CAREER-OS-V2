import pytest

from career_os.agents.fit_scorer import FitScorer
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceLedger, EvidenceSource, SupportStatus
from career_os.models.jd import JDAnalysis


def _ledger(*claims: str) -> EvidenceLedger:
    """Build a verified evidence ledger for focused scorer regression tests."""
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
    """Ensure a specific education mismatch is visible as risk, not a hard gap."""
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


@pytest.mark.parametrize(
    ("requirement", "claim"),
    [
        ("B.Tech degree", "B.Tech degree"),
        ("Bachelor's degree", "B.Com degree"),
        ("Master's degree", "MBA"),
        ("MBA degree", "MBA"),
    ],
)
def test_education_matching_handles_generic_levels_and_specific_families(requirement: str, claim: str) -> None:
    """Ensure generic bachelor/master requirements accept valid degree families."""
    jd = JDAnalysis(source_text="x", must_have_requirements=[requirement])
    result = FitScorer().score(jd, _ledger(claim))

    assert result.education_gaps == ()
    assert result.education_risk == "matched"
    assert result.hard_gaps == ()
    assert result.hard_requirements == 100.0


def test_education_only_mismatch_does_not_reduce_overall_fit() -> None:
    """Ensure adding an unmatched education requirement does not lower fit."""
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
    """Ensure unrelated hard requirements still block despite an education mismatch."""
    jd = JDAnalysis(source_text="x", must_have_requirements=["B.Tech degree", "Oracle"])
    result = FitScorer().score(jd, _ledger("B.Com degree"))

    assert result.education_gaps == ("B.Tech degree",)
    assert result.hard_gaps == ("Oracle",)
    assert result.recommendation == "hard_gap"


@pytest.mark.parametrize(
    "requirement",
    [
        "Master Data Management experience",
        "Master data management experience",
        "Master Data Management certification",
    ],
)
def test_master_data_management_is_not_education(requirement: str) -> None:
    """Ensure the domain term Master Data Management is never treated as a degree."""
    jd = JDAnalysis(source_text="x", must_have_requirements=[requirement])
    result = FitScorer().score(jd, _ledger("Master Data Management experience"))

    assert result.education_gaps == ()
    assert result.education_risk == "not_stated"
    assert result.hard_requirements == 100.0


def test_missing_master_data_management_remains_a_hard_gap() -> None:
    """Ensure a missing Master Data Management requirement still blocks a fit."""
    jd = JDAnalysis(source_text="x", must_have_requirements=["Master Data Management"])
    result = FitScorer().score(jd, _ledger("Python experience"))

    assert result.education_gaps == ()
    assert result.hard_gaps == ("Master Data Management",)
    assert result.recommendation == "hard_gap"
