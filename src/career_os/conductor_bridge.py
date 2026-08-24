"""Server-side bridge between Candor and the V2 Career OS pipeline.

This module is an adapter only. Candor can request deterministic V2 review,
but this boundary never submits an application or executes browser controls.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from career_os.models.evidence import (
    EvidenceClaim,
    EvidenceKind,
    EvidenceSource,
    SupportStatus,
)
from career_os.models.resume import ResumeBullet, ResumeProfile
from career_os.pipeline import CareerPipeline, PipelineResult


class ConductorBridgeRequest(BaseModel):
    profile: str = Field(min_length=1, max_length=200_000)
    job: dict[str, Any]
    idempotency_key: str = Field(min_length=8, max_length=200)
    resume: dict[str, Any] | None = None
    claims: list[dict[str, Any]] = Field(default_factory=list)
    browser_context: dict[str, Any] | None = None

    @field_validator("browser_context")
    @classmethod
    def reject_submission_controls(cls, value: dict[str, Any] | None):
        if not value:
            return value
        forbidden = {"submit_application", "auto_apply", "execute_application", "apply_now"}
        if any(key in forbidden for key in value):
            raise ValueError("automatic application submission is not supported by this boundary")
        return value


class IdempotencyStore:
    """Persist only request keys and trace metadata."""

    def __init__(self, path: str | None = None):
        self.path = Path(path or os.getenv("CAREER_OS_CONDUCTOR_IDEMPOTENCY_PATH", ".career_os/conductor_idempotency.json"))
        self._lock = threading.Lock()

    def _read(self) -> dict[str, dict[str, Any]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def reserve(self, key: str, trace_id: str) -> bool:
        with self._lock:
            records = self._read()
            if key in records:
                return False
            self.path.parent.mkdir(parents=True, exist_ok=True)
            records[key] = {"trace_id": trace_id, "reserved_at": int(time.time())}
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(records, separators=(",", ":")), encoding="utf-8")
            temp.replace(self.path)
            return True

    def release(self, key: str) -> None:
        with self._lock:
            records = self._read()
            records.pop(key, None)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(records, separators=(",", ":")), encoding="utf-8")
            temp.replace(self.path)


def _expected_token() -> str:
    return os.getenv("CAREER_OS_CONDUCTOR_TOKEN", "").strip()


def authorize(token: str | None) -> None:
    expected = _expected_token()
    if not expected or not token or not hmac.compare_digest(token, expected):
        raise PermissionError("valid Conductor service token required")


def _resume_from_request(payload: ConductorBridgeRequest) -> ResumeProfile:
    if payload.resume:
        bullets = tuple(
            ResumeBullet(
                text=str(item.get("text", "")),
                evidence_claim_ids=tuple(str(x) for x in item.get("evidence_claim_ids", [])),
            )
            for item in payload.resume.get("bullets", [])
            if str(item.get("text", "")).strip()
        )
        return ResumeProfile(
            summary=str(payload.resume.get("summary", "")).strip() or payload.profile,
            bullets=bullets,
        )
    # Backwards-compatible with the original Candor contract. A plain profile
    # is treated as summary-only; no unsupported claims are fabricated.
    return ResumeProfile(summary=payload.profile)


def _claims_from_request(payload: ConductorBridgeRequest) -> list[EvidenceClaim]:
    claims: list[EvidenceClaim] = []
    for index, item in enumerate(payload.claims):
        source_data = item.get("source")
        source = None
        if isinstance(source_data, dict):
            source = EvidenceSource(
                source_id=str(source_data.get("source_id", f"conductor-{index}")),
                source_type=str(source_data.get("source_type", "user_provided")),
                label=str(source_data.get("label", "Candor profile")),
            )
        claims.append(
            EvidenceClaim(
                claim_id=str(item.get("claim_id", f"conductor-claim-{index}")),
                claim=str(item.get("claim", "")),
                kind=EvidenceKind(str(item.get("kind", EvidenceKind.USER_PROVIDED.value))),
                support=SupportStatus(str(item.get("support", SupportStatus.SUPPORTED.value))),
                confidence=float(item.get("confidence", 0.8)),
                source=source,
                notes=str(item["notes"]) if item.get("notes") is not None else None,
            )
        )
    return claims


def run_v2_pipeline(payload: ConductorBridgeRequest, checkpoint_root: Path | None = None) -> PipelineResult:
    root = checkpoint_root or Path(os.getenv("CAREER_OS_CONDUCTOR_CHECKPOINT_PATH", ".career_os/conductor_runs"))
    run_id = hashlib.sha256(payload.idempotency_key.encode("utf-8")).hexdigest()[:24]
    checkpoint = root / f"{run_id}.json"
    return CareerPipeline(checkpoint).run(
        run_id=run_id,
        raw_job=payload.job,
        resume=_resume_from_request(payload),
        claims=_claims_from_request(payload),
    )


def result_to_dict(result: PipelineResult) -> dict[str, Any]:
    return {
        "checkpoint": asdict(result.checkpoint),
        "job": result.job.model_dump(mode="json"),
        "jd": asdict(result.jd),
        "ledger": result.ledger.to_dict(),
        "fit": asdict(result.fit),
        "tailored_resume": result.tailored_resume.to_dict(),
        "ats_audit": result.ats_audit.to_dict(),
        "recruiter_review": result.recruiter_review.to_dict(),
        "application_ready": result.application_ready,
        "application_mode": "REVIEW_ONLY",
        "submission_enabled": False,
    }
