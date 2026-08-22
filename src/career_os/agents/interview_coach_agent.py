from __future__ import annotations

from career_os.models.interview import (
    AnswerEvaluation,
    AnswerScore,
    InterviewQuestion,
    InterviewQuestionType,
)


class InterviewCoachAgent:
    """Deterministic interview planning and answer-coaching primitives."""

    def generate_questions(
        self,
        competencies: list[str],
        evidence: list[str],
        *,
        limit: int = 10,
    ) -> list[InterviewQuestion]:
        questions: list[InterviewQuestion] = []
        for competency in competencies[:limit]:
            questions.append(
                InterviewQuestion(
                    text=f"Tell me about a specific example demonstrating {competency}.",
                    question_type=InterviewQuestionType.ROLE_SPECIFIC,
                    competency=competency,
                    evidence_basis=evidence[:3],
                    follow_ups=[
                        "What was your specific contribution?",
                        "What was the measurable result?",
                        "What would you do differently?",
                    ],
                )
            )
        return questions

    def evaluate_answer(
        self,
        question: InterviewQuestion,
        answer: str,
        evidence: list[str],
    ) -> AnswerEvaluation:
        text = answer.strip()
        has_structure = any(marker in text.casefold() for marker in ("situation", "task", "action", "result"))
        score = AnswerScore(
            relevance=5 if question.competency.casefold() in text.casefold() else 2,
            structure=5 if has_structure else 2,
            specificity=5 if any(ch.isdigit() for ch in text) else 2,
            evidence=5 if evidence and any(item.casefold() in text.casefold() for item in evidence) else 1,
            clarity=5 if text else 0,
        )
        gaps: list[str] = []
        coaching: list[str] = []
        if not has_structure:
            gaps.append("Answer lacks a clear STAR-style structure.")
            coaching.append("Use Situation, Task, Action, and Result in that order.")
        if not any(ch.isdigit() for ch in text):
            gaps.append("Answer does not include a concrete measurable result.")
            coaching.append("Add a truthful metric, scale, time frame, or observable outcome when available.")
        unsupported = [] if not evidence else [item for item in evidence if item.casefold() not in text.casefold()]
        return AnswerEvaluation(
            question_id=question.question_id,
            score=score,
            strengths=["Answer was provided." if text else ""],
            gaps=gaps,
            coaching=coaching,
            evidence_used=[item for item in evidence if item.casefold() in text.casefold()],
            unsupported_claims=unsupported,
        )
