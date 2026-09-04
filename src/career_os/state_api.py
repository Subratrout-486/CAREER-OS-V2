"""Live HTTP endpoints for the durable execution store and dashboard.

These read from persisted state only - no external application action is ever
triggered through this read boundary. Approval / execution control remains
in the durable orchestration layer.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from career_os.dashboard.service import DashboardService
from career_os.execution.state import ExecutionStore


def _default_store_root() -> Path:
    return Path(os.getenv("CAREER_OS_EXECUTION_ROOT", ".career_os/executions"))


def create_state_router(
    *,
    store: ExecutionStore | None = None,
    dashboard: DashboardService | None = None,
) -> APIRouter:
    execution_store = store or ExecutionStore(_default_store_root())
    dashboard_service = dashboard or DashboardService(store=execution_store)
    router = APIRouter(prefix="/api/v1/state", tags=["state"])

    @router.get("/dashboard")
    def dashboard_snapshot() -> dict[str, Any]:
        return dashboard_service.snapshot()

    @router.get("/executions")
    def executions() -> dict[str, Any]:
        records = execution_store.list()
        return {
            "count": len(records),
            "executions": [
                {
                    "execution_id": e.execution_id,
                    "job_key": e.job_key,
                    "company": e.company,
                    "title": e.title,
                    "status": e.status,
                    "application_url": e.application_url,
                    "updated_at": e.updated_at,
                }
                for e in records
            ],
        }

    @router.get("/executions/{execution_id}")
    def execution(execution_id: str) -> dict[str, Any]:
        record = execution_store.load(execution_id)
        if record is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="execution not found")
        return {
            "execution_id": record.execution_id,
            "job_key": record.job_key,
            "company": record.company,
            "title": record.title,
            "status": record.status,
            "application_url": record.application_url,
            "events": [
                {"status": ev.status, "occurred_at": ev.occurred_at, "detail": ev.detail}
                for ev in record.events
            ],
        }

    return router
