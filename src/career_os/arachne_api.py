"""Direct HTTP boundary for the Arachne frontend."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from career_os.arachne_store import ArachneResultStore
from career_os.automation.job_processor import AutomaticJobProcessor, JobProcessingRequest
from career_os.conductor_bridge import IdempotencyStore, authorize, result_to_dict


class ArachneJobRequest(BaseModel):
    job: dict[str, Any]
    idempotency_key: str = Field(min_length=8, max_length=200)


def create_arachne_router(
    *,
    store: ArachneResultStore | None = None,
    processor_factory: Callable[[], AutomaticJobProcessor] | None = None,
    idempotency_store: IdempotencyStore | None = None,
) -> APIRouter:
    """Create the direct Arachne router.

    Production callers use the default implementations. Tests can inject
    isolated state and a fake processor without monkeypatching module globals.
    """
    router = APIRouter(prefix="/api/v1", tags=["arachne"])
    guard = idempotency_store or IdempotencyStore()
    result_store = store or ArachneResultStore(
        Path(os.getenv("CAREER_OS_ARACHNE_ROOT", ".career_os/arachne"))
    )
    make_processor = processor_factory or AutomaticJobProcessor

    def auth(token: str | None) -> None:
        try:
            authorize(token)
        except PermissionError as exc:
            raise HTTPException(
                status_code=401, detail="CareerOS API authorization required"
            ) from exc

    @router.get("/health")
    def health(x_career_os_token: str | None = Header(default=None)) -> dict[str, Any]:
        auth(x_career_os_token)
        return {
            "status": "ok",
            "service": "career-os-v2",
            "client": "arachne",
            "submission_enabled": False,
        }

    @router.get("/jobs")
    def jobs(x_career_os_token: str | None = Header(default=None)) -> dict[str, Any]:
        auth(x_career_os_token)
        results = result_store.list()
        return {"jobs": results, "count": len(results), "source": "career-os-v2"}

    @router.get("/jobs/{job_key:path}")
    def job(job_key: str, x_career_os_token: str | None = Header(default=None)) -> dict[str, Any]:
        auth(x_career_os_token)
        result = result_store.get(job_key)
        if result is None:
            raise HTTPException(status_code=404, detail="processed job not found")
        return result

    @router.post("/jobs")
    def process_job(
        request: Request,
        payload: ArachneJobRequest,
        x_career_os_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """Enter a job and immediately process it through CareerOS V2."""
        auth(x_career_os_token)
        host = request.client.host if request.client else "unknown"
        trace_id = hashlib.sha256(f"{payload.idempotency_key}:{host}".encode()).hexdigest()[:24]
        if not guard.reserve(payload.idempotency_key, trace_id):
            raise HTTPException(status_code=409, detail="idempotency key has already been used")
        try:
            result = make_processor().process(JobProcessingRequest(job=payload.job))
            serialized = result_to_dict(result)
            result_store.record(result.job.canonical_key, trace_id, serialized)
        except Exception as exc:
            guard.release(payload.idempotency_key)
            raise HTTPException(
                status_code=502,
                detail={"trace_id": trace_id, "error": "CareerOS processing failed"},
            ) from exc
        return {
            "trace_id": trace_id,
            "processing": "automatic",
            "submission_enabled": False,
            "result": serialized,
        }

    return router
