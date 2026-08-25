"""Direct HTTP boundary for the Arachne frontend."""
from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from career_os.automation.job_processor import AutomaticJobProcessor, JobProcessingRequest
from career_os.arachne_store import ArachneResultStore
from career_os.conductor_bridge import IdempotencyStore, authorize, result_to_dict


class ArachneJobRequest(BaseModel):
    job: dict[str, Any]
    idempotency_key: str = Field(min_length=8, max_length=200)


def create_arachne_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["arachne"])
    guard = IdempotencyStore()
    store = ArachneResultStore()

    def auth(token: str | None) -> None:
        try:
            authorize(token)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail="CareerOS API authorization required") from exc

    @router.get("/health")
    def health(x_career_os_token: str | None = Header(default=None)) -> dict[str, Any]:
        auth(x_career_os_token)
        return {"status": "ok", "service": "career-os-v2", "client": "arachne", "submission_enabled": False}

    @router.get("/jobs")
    def jobs(x_career_os_token: str | None = Header(default=None)) -> dict[str, Any]:
        auth(x_career_os_token)
        return {"jobs": store.list(), "count": len(store.list()), "source": "career-os-v2"}

    @router.get("/jobs/{job_key:path}")
    def job(job_key: str, x_career_os_token: str | None = Header(default=None)) -> dict[str, Any]:
        auth(x_career_os_token)
        result = store.get(job_key)
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
            result = AutomaticJobProcessor().process(JobProcessingRequest(job=payload.job))
            serialized = result_to_dict(result)
            store.record(result.job.canonical_key, trace_id, serialized)
        except Exception as exc:
            guard.release(payload.idempotency_key)
            raise HTTPException(status_code=502, detail={"trace_id": trace_id, "error": "CareerOS processing failed"}) from exc
        return {"trace_id": trace_id, "processing": "automatic", "submission_enabled": False, "result": serialized}
