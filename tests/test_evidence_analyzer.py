from career_os.agents.evidence_analyzer import EvidenceAnalyzer
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceSource, SupportStatus


def claim(claim_id, text, kind, support, source=None, confidence=0.9):
    return EvidenceClaim(
        claim_id=claim_id,
        claim=text,
        kind=kind,
        support=support,
        confidence=confidence,
        source=source,
    )


def test_build_ledger_preserves_provenance_and_deduplicates():
    source = EvidenceSource("resume-1", "resume", "Master resume")
    ledger = EvidenceAnalyzer().build_ledger([
        claim("c1", "Used Oracle SQL", EvidenceKind.VERIFIED, SupportStatus.SUPPORTED, source)
    ])
    assert ledger.supported()[0].source == source


def test_duplicate_claim_ids_are_rejected():
    analyzer = EvidenceAnalyzer()
    first = claim("c1", "Used SQL", EvidenceKind.USER_PROVIDED, SupportStatus.SUPPORTED)
    second = claim("c1", "Used Python", EvidenceKind.USER_PROVIDED, SupportStatus.SUPPORTED)
    try:
        analyzer.build_ledger([first, second])
        assert False, "duplicate evidence id should fail"
    except ValueError as exc:
        assert "Duplicate evidence claim id" in str(exc)


def test_unsupported_quantified_claim_cannot_enter_as_inference():
    analyzer = EvidenceAnalyzer()
    unsupported = claim("c1", "Reduced processing time by 40%", EvidenceKind.INFERRED, SupportStatus.UNSUPPORTED, confidence=0.2)
    try:
        analyzer.build_ledger([unsupported])
        assert False, "unsupported quantified claim should fail"
    except ValueError as exc:
        assert "Quantified outcomes" in str(exc)


def test_material_gaps_surface_inferred_or_unsupported_claims():
    analyzer = EvidenceAnalyzer()
    ledger = analyzer.build_ledger([
        claim("c1", "Used SQL", EvidenceKind.USER_PROVIDED, SupportStatus.SUPPORTED),
        claim("c2", "Python certification", EvidenceKind.UNKNOWN, SupportStatus.PARTIALLY_SUPPORTED, confidence=0.4),
    ])
    assert [item.claim_id for item in analyzer.material_gaps(ledger)] == ["c2"]
