"""Live dashboard state backed by persisted execution and provider state.

All metrics are computed from actual state - there are no fake/static numbers.
Provider health comes from the model router; application metrics come from the
durable execution store.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from career_os.execution.state import ExecutionStatus, ExecutionStore
from career_os.providers.routing import ModelRouter


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class DashboardService:
    """Compute a live dashboard snapshot from real persisted state."""

    def __init__(self, store: ExecutionStore | None = None, router: ModelRouter | None = None) -> None:
        self.store = store
        self.router = router or ModelRouter()

    def snapshot(self) -> dict[str, Any]:
        executions = self.store.list() if self.store else []
        by_status: dict[str, int] = {}
        for execution in executions:
            by_status[execution.status] = by_status.get(execution.status, 0) + 1

        high_fit = sum(
            1
            for e in executions
            if (e.pipeline.get("fit") or {}).get("overall", 0) >= 80
        )
        provider_health = self.router.health()

        latest = None
        if executions:
            latest = max(executions, key=lambda e: e.updated_at)
            latest = {
                "company": latest.company,
                "title": latest.title,
                "status": latest.status,
                "updated_at": latest.updated_at,
            }

        recent_errors = [
            {
                "company": e.company,
                "title": e.title,
                "status": e.status,
                "detail": e.execution.get("failure_reason") or e.execution.get("security_challenge") or "",
            }
            for e in sorted(executions, key=lambda x: x.updated_at, reverse=True)[:10]
            if e.status in {ExecutionStatus.APPLICATION_FAILED, ExecutionStatus.BLOCKED_SECURITY_CHALLENGE, ExecutionStatus.NEEDS_REVIEW}
        ]

        total = len(executions)
        submitted = by_status.get(ExecutionStatus.SUBMISSION_VERIFIED, 0) + by_status.get(ExecutionStatus.SUBMITTED, 0)
        pipeline_health = round(
            100.0 * (submitted + by_status.get(ExecutionStatus.READY_FOR_APPROVAL, 0) + by_status.get(ExecutionStatus.APPROVED, 0)) / total, 1
        ) if total else 100.0

        return {
            "generated_at": _utcnow(),
            "totals": {
                "jobs_discovered": len(executions),
                "jobs_analyzed": sum(
                    1 for e in executions if e.status not in {ExecutionStatus.DISCOVERED, ExecutionStatus.INTAKE_COMPLETE}
                ),
                "high_fit": high_fit,
                "awaiting_approval": by_status.get(ExecutionStatus.READY_FOR_APPROVAL, 0),
                "approved": by_status.get(ExecutionStatus.APPROVED, 0),
                "queued": by_status.get(ExecutionStatus.QUEUED, 0),
                "applying": by_status.get(ExecutionStatus.APPLYING, 0),
                "submitted": submitted,
                "failed": by_status.get(ExecutionStatus.APPLICATION_FAILED, 0),
                "blocked": by_status.get(ExecutionStatus.BLOCKED_SECURITY_CHALLENGE, 0),
                "needs_review": by_status.get(ExecutionStatus.NEEDS_REVIEW, 0),
            },
            "by_status": by_status,
            "provider_health": provider_health,
            "pipeline_health": pipeline_health,
            "latest_execution": latest,
            "recent_errors": recent_errors,
        }
