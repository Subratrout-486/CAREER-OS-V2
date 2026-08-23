from career_os.agents.interview_coach import InterviewCoach
from career_os.models.evidence import EvidenceClaim, EvidenceKind, EvidenceLedger, EvidenceSource, SupportStatus
from career_os.models.interview import InterviewQuestionType
from career_os.models.jd import JDAnalysis


def _ledger() -> EvidenceLedger:
    return EvidenceLedger((EvidenceClaim(
        claim_id="factset-support",
        claim="Resolved time and attendance support tickets using ServiceNow and SQL troubleshooting",
        kind=EvidenceKind.VERIFIED,
        support=SupportStatus.SUPPORTED,
        confidence=1.0,
        source=EvidenceSource("resume", "resume", "verified resume"),
    ),))


def test_prepare_generates_grounded_question_types():
    jd = JDAnalysis(
        source_text="test",
        must_have_requirements=["SQL"],
        responsibilities=["support tickets"],
        skills=["ServiceNow"],
    )
    questions = InterviewCoach().prepare(jd, _ledger())
    assert questions
    assert questions[0].question_type is InterviewQuestionType.TECHNICAL
    assert questions[0].evidence_basis == []
    assert any(q.competency == "ServiceNow" for q in questions)


def test_evaluate_rewards_evidence_and_structure():
    jd = JDAnalysis(source_text="test", must_have_requirements=["SQL"])
    question = InterviewCoach().prepare(jd, _ledger(), limit=1)[0]
    evaluation = InterviewCoach().evaluate_answer(
        question,
        "I resolved time and attendance support tickets using SQL troubleshooting. "
        "I investigated the issue, checked the relevant data, documented the resolution, "
        "and followed the ServiceNow workflow. The result was a clear, evidence-backed resolution.",
        _ledger(),
    )
    assert evaluation.score.evidence == 5
    assert evaluation.score.relevance == 5
    assert evaluation.score.total >= 20


def test_evaluate_flags_answers_without_candidate_evidence():
    jd = JDAnalysis(source_text="test", must_have_requirements=["Python"])
    question = InterviewCoach().prepare(jd, _ledger(), limit=1)[0]
    evaluation = InterviewCoach().evaluate_answer(
        question,
        "I would build a highly scalable platform and lead the architecture for it.",
        _ledger(),
    )
    assert evaluation.score.evidence == 1
    assert "No verified candidate evidence was clearly connected to the answer." in evaluation.gaps
