from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalRequired(RuntimeError):
    pass


@dataclass(frozen=True)
class ActionPolicy:
    """Default-deny policy for actions that cross Career OS safety boundaries."""

    approval_levels: frozenset[RiskLevel] = frozenset({RiskLevel.HIGH})
    blocked_tools: frozenset[str] = frozenset()

    def requires_approval(self, request: object) -> bool:
        name = getattr(request, "name", "")
        risk = RiskLevel(getattr(request, "risk", RiskLevel.LOW))
        if name in self.blocked_tools:
            raise ApprovalRequired(f"tool is blocked: {name}")
        return risk in self.approval_levels
