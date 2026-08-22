from __future__ import annotations

from career_os.models.learning import (
    LearningObjective,
    LearningPlan,
    LearningPriority,
    LearningResource,
    PracticeTask,
    ReadinessCheck,
)


class LearningAgent:
    """Builds small, evidence-gated learning plans from verified role gaps."""

    def build_plan(
        self,
        target_role: str,
        gaps: list[str],
        *,
        verified_skills: list[str] | None = None,
    ) -> LearningPlan:
        verified = {skill.casefold() for skill in (verified_skills or [])}
        objectives: list[LearningObjective] = []
        for raw_gap in gaps:
            skill = raw_gap.strip()
            if not skill or skill.casefold() in verified:
                continue
            priority = LearningPriority.CRITICAL if len(objectives) == 0 else LearningPriority.HIGH
            objectives.append(
                LearningObjective(
                    skill=skill,
                    priority=priority,
                    rationale=f"Close the verified {skill} gap for {target_role}.",
                    resources=[
                        LearningResource(
                            title=f"{skill} official documentation",
                            url=f"https://www.google.com/search?q={skill.replace(' ', '+')}+official+documentation",
                            provider="Official documentation search",
                            free=True,
                            reason="Use primary documentation before paid courses.",
                        )
                    ],
                    practice_tasks=[
                        PracticeTask(
                            title=f"Build a {skill} practice task",
                            objective=f"Demonstrate practical use of {skill} in a role-relevant scenario.",
                            deliverable=f"A reproducible {skill} exercise with notes and results.",
                            estimated_hours=3.0,
                        )
                    ],
                    readiness_checks=[
                        ReadinessCheck(
                            criterion=f"Can independently apply {skill} to a role-relevant task.",
                            evidence_required=f"Completed exercise demonstrating {skill} without fabricated experience.",
                        )
                    ],
                )
            )
        return LearningPlan(target_role=target_role, source_gaps=gaps, objectives=objectives)
