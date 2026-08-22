from __future__ import annotations
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class InterviewQuestionType(StrEnum):
    BEHAVIORAL = "BEHAVIORAL"
    TECHNICAL = "TECHNICAL"
    DOMAIN = "DOMAIN"
    ROLE_SPECIFIC = "ROLE_SPECIFIC"

class InterviewQuestion(BaseModel):
    question_id: UUID = Field(default_factory=uuid4)
    text: str
    question_type: InterviewQuestionType
    competency: str
    difficulty: int = Field(default=2, ge=1, le=3)
    evidence_basis: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)

class AnswerScore(BaseModel):
    relevance: int = Field(ge=0, le=5)
    structure: int = Field(ge=0, le=5)
    specificity: int = Field(ge=0, le=5)
    evidence: int = Field(ge=0, le=5)
    clarity: int = Field(ge=0, le=5)

    @property
    def total(self) -> int:
        return self.relevance + self.structure + self.specificity + self.evidence + self.clarity

class AnswerEvaluation(BaseModel):
    question_id: UUID
    score: AnswerScore
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    coaching: list[str] = Field(default_factory=list)
    evidence_used: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)

class InterviewSession(BaseModel):
    session_id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    started_at: datetime
    questions: list[InterviewQuestion] = Field(default_factory=list)
    evaluations: list[AnswerEvaluation] = Field(default_factory=list)
    completed_at: datetime | None = None

    @property
    def average_score(self) -> float | None:
        if not self.evaluations:
            return None
        return sum(e.score.total for e in self.evaluations) / (len(self.evaluations) * 25)
