from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable

from career_os.models.evidence import EvidenceClaim, EvidenceLedger, SupportStatus
from career_os.models.interview import (
    AnswerEvaluation,
    AnswerScore,
    InterviewQuestion,
    InterviewQuestionType,
    InterviewSession,
)
from career_os.models.jd import JDAnalysis


_STOPWORDS = {"the", "and", "for", "with", "from", "this", "that", "have", "has", "you", "your", "role"}


def _terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#.-]+", text.casefold())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _overlap(a: str, b: str) -> set[str]:
    return _terms(a).intersection(_terms(b))


def _supported_claims(ledger: EvidenceLedger) -> tuple[EvidenceClaim, ...]:
    return tuple(
        claim for claim in ledger.claims
        if claim.support in {SupportStatus.SUPPORTED, SupportStatus.PARTIALLY_SUPPORTED}
    )


class InterviewCoach:
    """Generate and evaluate interview practice from auditable JD evidence."""

    def prepare(
        self,
        jd: JDAnalysis,
        ledger: EvidenceLedger,
        *,
        limit: int = 10,
    ) -> list[InterviewQuestion]:
        if limit <= 0:
            raise ValueError("limit must be positive")

        claims = _supported_claims(ledger)
        questions: list[InterviewQuestion] = []

        for requirement in jd.must_have_requirements:
            evidence = [c for c in claims if _overlap(requirement, c.claim)]
            questions.append(
                InterviewQuestion(
                    text=f"How have you used {requirement} in your work?",
                    question_type=InterviewQuestionType.TECHNICAL,
                    competency=requirement,
                    difficulty=2,
                    evidence_basis=[c.claim_id for c in evidence[:3]],
                    follow_ups=[
                        "What was the problem you were solving?",
                        "What was your specific contribution?",
                    ],
                )
            )

        for responsibility in jd.responsibilities:
            evidence = [c for c in claims if _overlap(responsibility, c.claim)]
            questions.append(
                InterviewQuestion(
                    text=f"Tell me about a time you handled {responsibility}.",
                    question_type=InterviewQuestionType.BEHAVIORAL,
                    competency=responsibility,
                    difficulty=2,
                    evidence_basis=[c.claim_id for c in evidence[:3]],
                    follow_ups=[
                        "What action did you personally take?",
                        "What was the outcome and what did you learn?",
                    ],
                )
            )

        for skill in jd.skills:
            evidence = [c for c in claims if _overlap(skill, c.claim)]
            questions.append(
                InterviewQuestion(
                    text=f"How would you approach a problem involving {skill} in this role?",
                    question_type=InterviewQuestionType.ROLE_SPECIFIC,
                    competency=skill,
                    difficulty=2,
                    evidence_basis=[c.claim_id for c in evidence[:3]],
                    follow_ups=["What trade-offs would you consider?"],
                )
            )

        if not questions:
            questions.append(
                InterviewQuestion(
                    text="Walk me through your most relevant experience for this role.",
                    question_type=InterviewQuestionType.BEHAVIORAL,
                    competency="role fit",
                    difficulty=1,
                    evidence_basis=[c.claim_id for c in claims[:3]],
                    follow_ups=["What was your specific contribution?"],
                )
            )
        return questions[:limit]

    def evaluate_answer(
        self,
        question: InterviewQuestion,
        answer: str,
        ledger: EvidenceLedger,
    ) -> AnswerEvaluation:
        if not answer.strip():
            raise ValueError("answer cannot be empty")

        claims = _supported_claims(ledger)
        answer_terms = _terms(answer)
        question_terms = _terms(question.competency)
        evidence_used = [
            claim.claim_id
            for claim in claims
            if answer_terms.intersection(_terms(claim.claim))
        ]
        unsupported = [
            token for token in sorted(answer_terms - set().union(*(_terms(c.claim) for c in claims)) if claims else answer_terms)
            if token in {"led", "managed", "built", "designed", "owned", "architected"}
        ]

        relevance = 5 if question_terms and answer_terms.intersection(question_terms) else 2
        structure = 5 if len(answer.strip().split()) >= 35 else 3
        specificity = 5 if any(marker in answer.casefold() for marker in ("because", "by ", "using ", "when ")) else 3
        evidence = 5 if evidence_used else 1
        clarity = 5 if len(answer.strip().split()) <= 180 else 3
        score = AnswerScore(relevance, structure, specificity, evidence, clarity)

        gaps: list[str] = []
        coaching: list[str] = []
        if not evidence_used:
            gaps.append("No verified candidate evidence was clearly connected to the answer.")
            coaching.append("Anchor the answer in one verified experience and state your personal contribution.")
        if structure < 5:
            gaps.append("Answer lacks enough structure or detail for a strong interview response.")
            coaching.append("Use Situation, Task, Action, Result, then add one short reflection.")
        if specificity < 5:
            gaps.append("The answer does not clearly explain how or why the work was done.")
            coaching.append("Name the approach, tool, decision, or trade-off you actually used.")
        if unsupported:
            gaps.append("Potentially unsupported action claims detected: " + ", ".join(unsupported))
            coaching.append("Replace unsupported verbs with wording backed by the evidence ledger.")

        strengths = []
        if evidence_used:
            strengths.append("Connected the answer to recorded candidate evidence.")
        if relevance >= 5:
            strengths.append("Directly addressed the competency being tested.")
        if clarity >= 5:
            strengths.append("Answer length is suitable for an interview response.")

        return AnswerEvaluation(
            question_id=question.question_id,
            score=score,
            strengths=strengths,
            gaps=gaps,
            coaching=coaching,
            evidence_used=evidence_used,
            unsupported_claims=unsupported,
        )

    def start_session(self, job_id, questions: Iterable[InterviewQuestion]) -> InterviewSession:
        return InterviewSession(
            job_id=job_id,
            started_at=datetime.now(timezone.utc),
            questions=list(questions),
        )

    def prioritize(self, session: InterviewSession) -> list[str]:
        if not session.evaluations:
            return [question.competency for question in session.questions]
        by_question = {evaluation.question_id: evaluation for evaluation in session.evaluations}
        ranked = sorted(
            session.questions,
            key=lambda question: by_question.get(question.question_id).score.total if question.question_id in by_question else 0,
        )
        return [question.competency for question in ranked]
