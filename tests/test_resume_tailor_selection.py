from career_os.agents.resume_tailor import ResumeTailor, _MAX_TAILORED_BULLETS
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceLedger, EvidenceSource, SupportStatus
from career_os.models.jd import JDAnalysis
from career_os.models.resume import ResumeBullet, ResumeProfile


def _ledger(claims):
    source = EvidenceSource("test", "test", "test")
    return EvidenceLedger(tuple(
        EvidenceClaim(cid, text, EvidenceKind.VERIFIED, SupportStatus.SUPPORTED, 1.0, source)
        for cid, text in claims
    ))


def test_tailor_selects_relevant_subset_and_keeps_omitted_claims_traceable():
    bullets = tuple(
        ResumeBullet(f"SQL production troubleshooting responsibility {i}", (f"exp-factset-systems-{i}",))
        for i in range(12)
    ) + tuple(
        ResumeBullet(f"Customer support responsibility {i}", (f"exp-concentrix-{i}",))
        for i in range(10)
    )
    claims = [(cid, bullet.text) for bullet in bullets for cid in bullet.evidence_claim_ids]
    resume = ResumeProfile("Support engineer.", bullets)
    jd = JDAnalysis(source_text="test", must_have_requirements=["SQL"], skills=["SQL"])

    result = ResumeTailor().tailor(resume, jd, _ledger(claims))

    assert len(result.bullets) == _MAX_TAILORED_BULLETS
    assert len(result.omitted_claim_ids) == len(claims) - _MAX_TAILORED_BULLETS
    assert any(cid.startswith("exp-concentrix-") for bullet in result.bullets for cid in bullet.evidence_claim_ids)
    assert "one-page" in " ".join(result.edit_trace).casefold()


def test_tailor_never_selects_unsupported_claims():
    source = EvidenceSource("test", "test", "test")
    ledger = EvidenceLedger((
        EvidenceClaim("supported", "SQL troubleshooting", EvidenceKind.VERIFIED, SupportStatus.SUPPORTED, 1.0, source),
        EvidenceClaim("unsupported", "Python development", EvidenceKind.USER_PROVIDED, SupportStatus.UNSUPPORTED, 0.0),
    ))
    resume = ResumeProfile("Support engineer.", (
        ResumeBullet("SQL troubleshooting", ("supported",)),
        ResumeBullet("Python development", ("unsupported",)),
    ))
    jd = JDAnalysis(source_text="test", skills=["SQL", "Python"])

    result = ResumeTailor().tailor(resume, jd, ledger)

    assert [b.text for b in result.bullets] == ["SQL troubleshooting"]
    assert result.omitted_claim_ids == ()
