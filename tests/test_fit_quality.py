from career_os.agents.fit_scorer import FitScorer
from career_os.agents.jd_intelligence import JDIntelligence
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceLedger, EvidenceSource, SupportStatus
from career_os.models.jd import JDAnalysis


def _ledger(*claims: str) -> EvidenceLedger:
    return EvidenceLedger(tuple(
        EvidenceClaim(
            claim_id=f"c{i}",
            claim=claim,
            kind=EvidenceKind.VERIFIED,
            support=SupportStatus.SUPPORTED,
            confidence=1.0,
            source=EvidenceSource("test", "test", "test evidence"),
        )
        for i, claim in enumerate(claims, start=1)
    ))


def test_unstructured_jd_is_marked_weak_and_cannot_score_as_strong_fit():
    jd = JDIntelligence().analyze(
        "Account Executive role. Build relationships with customers and drive growth. "
        "Experience with sales and Salesforce is useful."
    )

    assert jd.analysis_quality == "weak"
    assert jd.must_have_requirements == []
    assert jd.preferred_requirements == []

    fit = FitScorer().score(jd, _ledger("Used Salesforce to manage customer opportunities."))

    assert fit.jd_quality == "weak"
    assert fit.overall <= 60.0
    assert fit.recommendation == "insufficient_jd"


def test_empty_jd_analysis_is_not_a_perfect_fit():
    jd = JDAnalysis(source_text="Only a job title")

    fit = FitScorer().score(jd, _ledger("Strong SQL and Unix support experience."))

    assert fit.jd_quality == "insufficient"
    assert fit.overall == 0.0
    assert fit.recommendation == "insufficient_jd"


def test_structured_jd_can_still_reach_full_fit_when_evidence_matches():
    jd = JDAnalysis(
        source_text="Support role",
        must_have_requirements=["SQL"],
        preferred_requirements=["REST API"],
        skills=["ServiceNow"],
        analysis_quality="strong",
    )
    fit = FitScorer().score(
        jd,
        _ledger(
            "Resolved production incidents using SQL troubleshooting.",
            "Worked with REST APIs and ServiceNow.",
        ),
    )

    assert fit.jd_quality == "strong"
    assert fit.overall == 100.0
    assert fit.recommendation == "strong_fit"
