import pytest

from career_os.models.evidence import (
    EvidenceClaim,
    EvidenceKind,
    EvidenceSource,
    SupportStatus,
)


def test_verified_claim_requires_provenance():
    with pytest.raises(ValueError, match="Verified evidence requires a source"):
        EvidenceClaim(
            claim_id="c1",
            claim="Used SQL",
            kind=EvidenceKind.VERIFIED,
            support=SupportStatus.SUPPORTED,
            confidence=0.9,
        )


def test_unsupported_claim_cannot_have_high_confidence():
    with pytest.raises(ValueError, match="Unsupported evidence cannot have confidence above 0.5"):
        EvidenceClaim(
            claim_id="c2",
            claim="Built an unsupported system",
            kind=EvidenceKind.USER_PROVIDED,
            support=SupportStatus.UNSUPPORTED,
            confidence=0.9,
        )


def test_supported_claim_can_keep_source():
    source = EvidenceSource("resume-1", "resume", "Master resume")
    claim = EvidenceClaim(
        claim_id="c3",
        claim="Used Excel",
        kind=EvidenceKind.VERIFIED,
        support=SupportStatus.SUPPORTED,
        confidence=1.0,
        source=source,
    )
    assert claim.source == source
