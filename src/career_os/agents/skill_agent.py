from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from career_os.core.skills import SkillDefinition, SkillRegistry


@dataclass(frozen=True)
class AgentContext:
    """Runtime context exposed to a skill-backed agent."""

    skill: SkillDefinition


class SkillBackedAgent:
    """Bind an executable agent to a validated Agent Skill.

    The skill supplies procedural knowledge; deterministic business logic remains
    in the agent implementation instead of being hidden inside a prompt.
    """

    skill_name: str

    def __init__(self, *, skills_root: Path | None = None) -> None:
        root = skills_root or self._default_skills_root()
        self.registry = SkillRegistry(root)
        self.context = AgentContext(skill=self.registry.get(self.skill_name))

    @staticmethod
    def _default_skills_root() -> Path:
        return Path(__file__).resolve().parents[3] / "skills"

    @property
    def instructions(self) -> str:
        return self.context.skill.instructions

    def execute(self, operation: Callable[[], Any]) -> Any:
        """Execute deterministic agent work under the selected skill contract."""

        return operation()
