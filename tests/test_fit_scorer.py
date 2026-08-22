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


def test_fit_score_is_traceable_and_weighted() -> None:
    jd = JDAnalysis(
        source_text="x",
        must_have_requirements=["Python", "SQL"],
        preferred_requirements=["Power BI"],
        skills=["Python", "SQL", "Power BI"],
    )
    result = FitScorer().score(jd, _ledger("Used Python and SQL", "Built Power BI dashboards"))

    assert result.overall == 100.0
    assert result.recommendation == "strong_fit"
    assert result.hard_gaps == ()
    assert set(result.evidence_claim_ids) == {"c1", "c2"}


def test_missing_must_have_is_a_hard_gap() -> None:
    jd = JDAnalysis(source_text="x", must_have_requirements=["Python", "Oracle"])
    result = FitScorer().score(jd, _ledger("Used Python in support work"))

    assert result.hard_requirements == 50.0
    assert result.hard_gaps == ("Oracle",)
    assert result.recommendation == "hard_gap"


def test_unsupported_evidence_cannot_inflate_fit() -> None:
    jd = JDAnalysis(source_text="x", must_have_requirements=["Python"])
    ledger = EvidenceLedger().add(
        EvidenceClaim(
            claim_id="c1",
            claim="Python",
            kind=EvidenceKind.USER_PROVIDED,
            support=SupportStatus.UNSUPPORTED,
            confidence=0.5,
        )
    )
    result = FitScorer().score(jd, ledger)

    assert result.hard_requirements == 0.0
    assert result.hard_gaps == ("Python",)
    assert result.recommendation == "hard_gap"


def test_common_skill_aliases_match_without_changing_source_evidence() -> None:
    jd = JDAnalysis(
        source_text="x",
        must_have_requirements=["Power BI", "PostgreSQL", "REST API", "AWS"],
        skills=["Power BI", "PostgreSQL", "REST API", "AWS"],
    )
    result = FitScorer().score(
        jd,
        _ledger("Built PowerBI dashboards", "Used Postgres", "Integrated RESTful APIs", "Worked with Amazon Web Services"),
    )

    assert result.hard_requirements == 100.0
    assert result.hard_gaps == ()
    assert result.recommendation == "strong_fit"


def test_nosql_does_not_match_sql_requirement() -> None:
    jd = JDAnalysis(source_text="x", must_have_requirements=["SQL"])
    result = FitScorer().score(jd, _ledger("Worked with NoSQL databases"))

    assert result.hard_requirements == 0.0
    assert result.hard_gaps == ("SQL",)
    assert result.recommendation == "hard_gap"
