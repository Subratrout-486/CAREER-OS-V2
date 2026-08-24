from __future__ import annotations

import json
from pathlib import Path

import pytest

from career_os.conductor_bridge import (
    ConductorBridgeRequest,
    IdempotencyStore,
    _claims_from_request,
    _resume_from_request,
    authorize,
)


def test_plain_profile_is_summary_only() -> None:
    payload = ConductorBridgeRequest(
        profile="Subrat profile text",
        job={"company": "Example", "title": "Support Engineer", "source_url": "https://example.com/jobs/1", "description": "SQL support"},
        idempotency_key="plain-profile-1",
    )
    resume = _resume_from_request(payload)
    assert resume.summary == "Subrat profile text"
    assert resume.bullets == ()
    assert _claims_from_request(payload) == []


def test_structured_resume_and_claims_are_preserved() -> None:
    payload = ConductorBridgeRequest(
        profile="fallback",
        job={"company": "Example", "title": "Support Engineer", "source_url": "https://example.com/jobs/1", "description": "SQL support"},
        idempotency_key="structured-1",
        resume={"summary": "Support engineer", "bullets": [{"text": "Troubleshot SQL incidents", "evidence_claim_ids": ["c1"]}]},
        claims=[
            {
                "claim_id": "c1",
                "claim": "Troubleshot SQL incidents",
                "kind": "user_provided",
                "support": "supported",
                "confidence": 0.9,
            }
        ],
    )
    assert _resume_from_request(payload).bullets[0].evidence_claim_ids == ("c1",)
    assert _claims_from_request(payload)[0].claim_id == "c1"


def test_submission_controls_are_rejected() -> None:
    with pytest.raises(ValueError):
        ConductorBridgeRequest(
            profile="x",
            job={"company": "Example", "title": "Support", "source_url": "https://example.com/1", "description": "x"},
            idempotency_key="blocked-1",
            browser_context={"auto_apply": True},
        )


def test_idempotency_store_only_contains_metadata(tmp_path: Path) -> None:
    path = tmp_path / "idempotency.json"
    store = IdempotencyStore(str(path))
    assert store.reserve("key-123456", "trace-1") is True
    assert store.reserve("key-123456", "trace-2") is False
    data = json.loads(path.read_text())
    assert data == {"key-123456": {"trace_id": "trace-1", "reserved_at": data["key-123456"]["reserved_at"]}}
    assert "profile" not in data["key-123456"]
    assert "job" not in data["key-123456"]


def test_authorize_requires_matching_server_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAREER_OS_CONDUCTOR_TOKEN", "secret")
    authorize("secret")
    with pytest.raises(PermissionError):
        authorize("wrong")
    with pytest.raises(PermissionError):
        authorize(None)
