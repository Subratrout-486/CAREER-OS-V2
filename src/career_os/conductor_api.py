"""FastAPI boundaries used by Candor and AgentFlow integrations."""
from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from career_os.agentflow_client import AgentFlowClient, AgentFlowError
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


class AgentFlowObjectiveRequest(BaseModel):
    """Optional model work delegated to AgentFlow Studio."""

    objective: str = Field(min_length=1, max_length=100_000)
    workflow: str = Field(default="CAREER OS V2", min_length=1, max_length=160)
    provider: str = Field(default="auto", min_length=1, max_length=40)
    nodes: list[dict[str, Any]] | None = None


def create_conductor_router() -> APIRouter:
    router = APIRouter(prefix="/api/conductor/v1", tags=["conductor"])
    replay_guard = IdempotencyStore()

    @router.get("/health")
    def health(x_conductor_token: str | None = Header(default=None)) -> dict[str, Any]:
        try:
            authorize(x_conductor_token)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        agentflow = AgentFlowClient()
        return {
            "status": "ok",
            "boundary": "career-os-v2",
            "review_only": True,
            "engine": "career-os-v2-pipeline",
            "submission": "disabled",
            "agentflow": {"configured": agentflow.config.enabled, "base_url": agentflow.config.base_url},
            "capabilities": [
                "pipeline.review",
                "readiness.evaluate",
                "evidence.validate",
                "ats.audit",
                "job.intake.auto_process",
                "ai.delegate.agentflow",
            ],
        }

    @router.post("/ai/objective")
    def delegate_ai_objective(
        payload: AgentFlowObjectiveRequest,
        x_conductor_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """Delegate optional nondeterministic model work without changing V2's core pipeline."""
        try:
            authorize(x_conductor_token)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        try:
            return AgentFlowClient().submit_objective(
                payload.objective,
                workflow=payload.workflow,
                provider=payload.provider,
                nodes=payload.nodes,
            )
        except AgentFlowError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @router.get("/ai/runs/{run_id}")
    def get_ai_run(run_id: str, x_conductor_token: str | None = Header(default=None)) -> dict[str, Any]:
        try:
            authorize(x_conductor_token)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        try:
            return AgentFlowClient().get_run(run_id)
        except AgentFlowError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

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
