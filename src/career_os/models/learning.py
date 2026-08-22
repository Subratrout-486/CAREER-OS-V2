from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class LearningPriority(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class LearningResource(BaseModel):
    title: str
    url: str
    provider: str
    free: bool = False
    reason: str


class PracticeTask(BaseModel):
    title: str
    objective: str
    deliverable: str
    estimated_hours: float = Field(gt=0, le=100)


class ReadinessCheck(BaseModel):
    criterion: str
    evidence_required: str
    passed: bool = False


class LearningObjective(BaseModel):
    objective_id: UUID = Field(default_factory=uuid4)
    skill: str
    priority: LearningPriority
    rationale: str
    prerequisites: list[str] = Field(default_factory=list)
    resources: list[LearningResource] = Field(default_factory=list)
    practice_tasks: list[PracticeTask] = Field(default_factory=list)
    readiness_checks: list[ReadinessCheck] = Field(default_factory=list)


class LearningPlan(BaseModel):
    target_role: str
    source_gaps: list[str] = Field(default_factory=list)
    objectives: list[LearningObjective] = Field(default_factory=list)
    completion_evidence: list[str] = Field(default_factory=list)
