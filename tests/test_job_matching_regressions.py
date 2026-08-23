from career_os.agents.fit_scorer import FitScorer
from career_os.agents.jd_intelligence import JDIntelligence
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceLedger, EvidenceSource, SupportStatus


SOURCE = EvidenceSource("test/source", "test", "Regression test evidence")


def claim(claim_id: str, text: str) -> EvidenceClaim:
    return EvidenceClaim(claim_id, text, EvidenceKind.VERIFIED, SupportStatus.SUPPORTED, 1.0, SOURCE)


def test_jd_parser_does_not_turn_boilerplate_into_hard_requirements():
    jd = JDIntelligence().analyze(
        """Qualifications:\nEducation:\nBachelor’s degree in any discipline or equivalent\nExperience:\n1-3 year of related experience is required.\nTechnical Skills:\nBasic knowledge of Unix/Linux operating systems.\nBasic understanding of SQL queries.\nFamiliarity with file transfer mechanisms (FTP, SFTP or similar).\nUnderstanding of cloud computing concepts, including basic cloud setup and infrastructure (VMs, storage, networking fundamentals).\nRelevant Skills:\nProblem Solving\nGood verbal and written communication skills.\nSuccess Profile\nLeading Complexity\nBrightstar is committed to sustaining a workforce that reflects diversity.\nApply now"""
    )
    assert jd.must_have_requirements == (
        "Bachelor’s degree in any discipline or equivalent",
        "1-3 year of related experience is required.",
        "Basic knowledge of Unix/Linux operating systems.",
        "Basic understanding of SQL queries.",
        "Familiarity with file transfer mechanisms (FTP, SFTP or similar).",
        "Understanding of cloud computing concepts, including basic cloud setup and infrastructure (VMs, storage, networking fundamentals).",
    )
    assert all("Brightstar is committed" not in item for item in jd.must_have_requirements)
    assert all("Success Profile" not in item for item in jd.must_have_requirements)


def test_fit_scorer_matches_semantic_core_of_objective_requirements():
    jd = JDIntelligence().analyze(
        """Qualifications:\nBachelor’s degree in any discipline or equivalent\n1-3 year of related experience is required.\nBasic knowledge of Unix/Linux operating systems.\nBasic understanding of SQL queries.\nFamiliarity with file transfer mechanisms (FTP, SFTP or similar).\nUnderstanding of cloud computing concepts, including basic cloud setup and infrastructure (VMs, storage, networking fundamentals)."""
    )
    ledger = EvidenceLedger()
    for item in (
        claim("education", "Education: Bachelor of Commerce (Accounting Hons) degree"),
        claim("experience", "Professional support experience: nearly 3 years"),
        claim("unix", "FactSet: Linux/Unix production support"),
        claim("sql", "FactSet: SQL and PL/SQL investigation"),
    ):
        ledger = ledger.add(item)

    result = FitScorer().score(jd, ledger)
    assert "Bachelor’s degree in any discipline or equivalent" not in result.hard_gaps
    assert "1-3 year of related experience is required." not in result.hard_gaps
    assert "Basic knowledge of Unix/Linux operating systems." not in result.hard_gaps
    assert "Basic understanding of SQL queries." not in result.hard_gaps
    assert any("FTP" in gap for gap in result.hard_gaps)
    assert any("cloud computing" in gap.casefold() for gap in result.hard_gaps)
    assert result.recommendation == "hard_gap"
