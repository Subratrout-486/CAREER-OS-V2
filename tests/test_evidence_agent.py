from career_os.agents.evidence_agent import EvidenceAgent
from career_os.models.evidence import EvidenceKind, SupportStatus


def test_evidence_agent_preserves_provenance_and_support():
    ledger = EvidenceAgent().build_ledger([
        {
            "claim_id": "fact-1",
            "claim": "Used SQL for production support",
            "kind": "verified",
            "support": "supported",
            "confidence": 0.95,
        },
        {
            "claim_id": "fact-2",
            "claim": "Developed a proprietary AI platform",
            "kind": "user_provided",
            "support": "unsupported",
            "confidence": 0.4,
        },
    ])

    assert len(ledger.claims) == 2
    assert ledger.claims[0].source is not None
    assert ledger.claims[0].kind is EvidenceKind.VERIFIED
    assert ledger.claims[1].support is SupportStatus.UNSUPPORTED
    assert len(ledger.supported()) == 1
    assert len(ledger.unsupported()) == 1


def test_verified_claim_requires_source_and_unsupported_claim_is_capped():
    agent = EvidenceAgent()
    ledger = agent.build_ledger([
        {"claim": "Worked with Oracle", "kind": "verified", "confidence": 0.9},
        {"claim": "Managed a billion-dollar portfolio", "support": "unsupported", "confidence": 0.2},
    ])

    assert ledger.claims[0].source is not None
    assert ledger.claims[1].confidence == 0.2


def test_requirement_matching_uses_only_supported_evidence():
    ledger = EvidenceAgent().build_ledger([
        {"claim": "Advanced Excel and SQL experience", "support": "supported"},
        {"claim": "Python expertise", "support": "unsupported", "confidence": 0.2},
    ])

    matches = EvidenceAgent().claims_for_requirement(ledger, "SQL experience")
    assert [claim.claim for claim in matches] == ["Advanced Excel and SQL experience"]
