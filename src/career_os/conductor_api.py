"""FastAPI boundary used by Candor's server-side Conductor proxy."""
from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from career_os.automation.job_processor import AutomaticJobProcessor, JobProcessingRequest
from career_os.conductor_bridge import (
    ConductorBridgeRequest,
    IdempotencyStore,
    authorize,
    result_to_dict,
    run_v2_pipeline,
)


class AutomaticJobIntakeRequest(BaseModel):
    """A discovered job enters V2 and is processed immediately."""

    job: dict[str, Any]
    idempotency_key: str = Field(min_length=8, max_length=200)


def create_conductor_router() -> APIRouter:
    router = APIRouter(prefix="/api/conductor/v1", tags=["conductor"])
    replay_guard = IdempotencyStore()

    @router.get("/health")
    def health(x_conductor_token: str | None = Header(default=None)) -> dict[str, Any]:
        try:
            authorize(x_conductor_token)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return {
            "status": "ok",
            "boundary": "career-os-v2",
            "review_only": True,
            "engine": "career-os-v2-pipeline",
            "submission": "disabled",
            "capabilities": [
                "pipeline.review",
                "readiness.evaluate",
                "evidence.validate",
                "ats.audit",
                "job.intake.auto_process",
            ],
        }

    @router.post("/jobs/intake")
    def intake_job(
        request: Request,
        payload: AutomaticJobIntakeRequest,
        x_conductor_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """Accept a job and immediately run the complete CareerOS V2 pipeline."""
        try:
            authorize(x_conductor_token)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        trace_seed = f"{payload.idempotency_key}:{request.client.host if request.client else 'unknown'}"
        trace_id = hashlib.sha256(trace_seed.encode("utf-8")).hexdigest()[:24]
        if not replay_guard.reserve(payload.idempotency_key, trace_id):
            raise HTTPException(status_code=409, detail="idempotency key has already been used")

        try:
            result = AutomaticJobProcessor().process(JobProcessingRequest(job=payload.job))
        except Exception as exc:
            replay_guard.release(payload.idempotency_key)
            raise HTTPException(
                status_code=502,
                detail={"trace_id": trace_id, "error": "automatic CareerOS V2 processing failed"},
            ) from exc

        return {
            "boundary": "career-os-v2",
            "trace_id": trace_id,
            "idempotency_key": payload.idempotency_key,
            "processing": "automatic",
            "review_only": True,
            "result": result_to_dict(result),
        }

    @router.post("/pipeline/run")
    def run_pipeline(
        request: Request,
        payload: ConductorBridgeRequest,
        x_conductor_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        try:
            authorize(x_conductor_token)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        trace_seed = f"{payload.idempotency_key}:{request.client.host if request.client else 'unknown'}"
        trace_id = hashlib.sha256(trace_seed.encode("utf-8")).hexdigest()[:24]
        if not replay_guard.reserve(payload.idempotency_key, trace_id):
            raise HTTPException(status_code=409, detail="idempotency key has already been used")

        try:
            result = run_v2_pipeline(payload)
        except Exception as exc:
            replay_guard.release(payload.idempotency_key)
            raise HTTPException(
                status_code=502,
                detail={"trace_id": trace_id, "error": "career-os-v2 pipeline failed"},
            ) from exc

        return {
            "boundary": "career-os-v2",
            "trace_id": trace_id,
            "idempotency_key": payload.idempotency_key,
            "review_only": True,
            "result": result_to_dict(result),
        }

    return router


try:
    from fastapi import FastAPI
except ImportError:  # pragma: no cover - keeps the core package usable without HTTP extras
    FastAPI = None  # type: ignore[assignment]


if FastAPI is not None:
    app = FastAPI(title="Career OS V2 Conductor Boundary")
    app.include_router(create_conductor_router())
else:  # pragma: no cover
    app = None
