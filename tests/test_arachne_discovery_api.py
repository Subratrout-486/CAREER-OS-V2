"""Tests for the real ATS discovery endpoint on the ARACHNE control plane.

Uses isolated stores (tmp_path) and an injected fake ATS discovery service so no
live network is contacted. The endpoint must never report success when a source
is unsupported, empty, or unreachable.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from career_os.arachne_control import create_arachne_control_router
from career_os.arachne_store import ArachneResultStore
from career_os.dashboard.service import DashboardService
from career_os.execution.state import ExecutionStore
from career_os.integrations.ats import RawATSJob
from career_os.integrations.ats_discovery import DiscoveryResult
from career_os.providers.routing import ModelRouter

CANDIDATE = Path("candidate/source_of_truth.json")


class FakeATSDiscovery:
    """Injected discovery service; returns whatever the test configures."""

    def __init__(self, provider=None, jobs=()):
        self._provider = provider
        self._jobs = tuple(jobs)

    def scan(self, careers_url, *, max_jobs=100):
        return DiscoveryResult(careers_url, self._provider, tuple(self._jobs[:max_jobs]))


def _job() -> RawATSJob:
    return RawATSJob(
        provider="greenhouse",
        external_id="g-123",
        company="Acme",
        title="Support Engineer",
        location="India",
        description=(
            "Hiring a Support Engineer. Troubleshoot application failures and "
            "data inconsistencies across Oracle databases and Linux servers. "
            "Strong SQL, Python automation, REST API validation, and root-cause "
            "analysis required."
        ),
        job_url="https://boards.greenhouse.io/acme/jobs/g-123",
        posted_at=None,
        raw={},
    )


def _client(tmp_path, discovery):
    api = FastAPI()
    exec_store = ExecutionStore(tmp_path / "exec")
    api.include_router(
        create_arachne_control_router(
            execution_store=exec_store,
            result_store=ArachneResultStore(tmp_path / "arachne"),
            dashboard=DashboardService(store=exec_store, router=ModelRouter()),
            router=ModelRouter(),
            candidate_path=CANDIDATE,
            ats_discovery=discovery,
        )
    )
    return TestClient(api), exec_store


def test_discover_prepares_real_ats_jobs(tmp_path):
    client, store = _client(tmp_path, FakeATSDiscovery(provider="greenhouse", jobs=[_job()]))
    resp = client.post("/api/discover", json={"careers_url": "https://boards.greenhouse.io/acme"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "greenhouse"
    assert body["status"] == "ok"
    assert body["blocked"] is False
    assert body["jobs_scanned"] == 1
    assert body["unique_jobs"] == 1
    assert body["duplicates"] == 0
    assert body["prepared"] == 1
    assert len(body["execution_ids"]) == 1

    # The prepared execution is persisted and full analytic artifacts are present.
    exc = store.load(body["execution_ids"][0])
    assert exc is not None
    assert exc.status == "READY_FOR_APPROVAL"
    assert exc.job_key
    assert exc.company == "Acme"
    for key in ("jd", "evidence", "fit", "profile", "ats_audit", "recruiter_review"):
        assert exc.pipeline.get(key)

    # It is visible in the approval queue and in the job list.
    assert client.get("/api/approval-queue").json()["count"] == 1
    assert client.get("/api/jobs").json()["count"] == 1


def test_discover_unsupported_url_is_blocked_not_success(tmp_path):
    client, _ = _client(tmp_path, FakeATSDiscovery(provider=None, jobs=()))
    resp = client.post("/api/discover", json={"careers_url": "https://unknown.example.com/careers"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] is None
    assert body["status"] == "unsupported"
    assert body["blocked"] is True
    assert body["prepared"] == 0
    assert body["execution_ids"] == []
    assert "No supported ATS provider" in body["reason"]
    # Nothing is falsely queued for approval.
    assert client.get("/api/approval-queue").json()["count"] == 0


def test_discover_degraded_when_provider_returns_nothing(tmp_path):
    client, _ = _client(tmp_path, FakeATSDiscovery(provider="greenhouse", jobs=()))
    body = client.post(
        "/api/discover", json={"careers_url": "https://boards.greenhouse.io/acme"}
    ).json()
    assert body["provider"] == "greenhouse"
    assert body["status"] == "degraded"
    assert body["blocked"] is True
    assert body["prepared"] == 0
    assert body["jobs_scanned"] == 0


def test_discover_requires_careers_url(tmp_path):
    client, _ = _client(tmp_path, FakeATSDiscovery())
    assert client.post("/api/discover", json={}).status_code == 400
    assert client.post("/api/discover", json={"careers_url": "   "}).status_code == 400


def test_discover_marks_duplicates(tmp_path):
    # Two identical raw jobs collapse to one unique job.
    client, _ = _client(tmp_path, FakeATSDiscovery(provider="lever", jobs=[_job(), _job()]))
    body = client.post("/api/discover", json={"careers_url": "https://jobs.lever.co/acme"}).json()
    assert body["provider"] == "lever"
    assert body["jobs_scanned"] == 2
    assert body["unique_jobs"] == 1
    assert body["duplicates"] == 1
    assert body["prepared"] == 1
