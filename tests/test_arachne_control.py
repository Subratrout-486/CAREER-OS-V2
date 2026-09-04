"""Tests for the ARACHNE live control-plane API.

Uses isolated stores (tmp_path) so no project state is touched. Candidate
source of truth is read from the committed fixture; all other endpoints read
only real, in-test persisted/generated data - there are no hardcoded metrics.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from career_os.arachne_control import create_arachne_control_router
from career_os.arachne_store import ArachneResultStore
from career_os.dashboard.service import DashboardService
from career_os.execution.state import ExecutionStore
from career_os.providers.routing import ModelRouter

CANDIDATE = Path("candidate/source_of_truth.json")


@pytest.fixture()
def control(tmp_path):
    api = FastAPI()
    exec_store = ExecutionStore(tmp_path / "exec")
    api.include_router(
        create_arachne_control_router(
            execution_store=exec_store,
            result_store=ArachneResultStore(tmp_path / "arachne"),
            dashboard=DashboardService(store=exec_store, router=ModelRouter()),
            router=ModelRouter(),
            candidate_path=CANDIDATE,
        )
    )
    return TestClient(api)


def test_overview_empty_returns_real_zero_metrics(control):
    data = control.get("/api/overview").json()
    assert data["totals"]["jobs_discovered"] == 0
    assert data["approval_queue_count"] == 0
    assert data["pipeline_health"] == 100.0
    assert "generated_at" in data


def test_discover_demo_prepares_ready_application(control):
    r = control.post("/api/discover-demo")
    assert r.status_code == 200
    body = r.json()
    assert body["prepared"] == 1
    jid = body["first_execution_id"]
    assert jid

    jobs = control.get("/api/jobs").json()
    assert jobs["count"] == 1
    queue = control.get("/api/approval-queue").json()
    assert queue["count"] == 1
    assert queue["items"][0]["execution_id"] == jid


def test_job_detail_contains_full_analytic_pipeline(control):
    jid = control.post("/api/discover-demo").json()["first_execution_id"]
    job = control.get(f"/api/jobs/{jid}").json()
    assert job["title"] == "Support Engineer"
    assert job["company"] == "Acme"
    assert job["status"] == "READY_FOR_APPROVAL"
    # full analytic artifacts are persisted (not hardcoded)
    assert job["fit"] and "overall" in job["fit"]
    assert job["jd"] and "must_have_requirements" in job["jd"]
    assert isinstance(job["evidence"], list) and job["evidence"]
    assert job["ats_audit"] and "score" in job["ats_audit"]
    assert job["recruiter_review"] and "recommendation" in job["recruiter_review"]
    assert job["profile"] and isinstance(job["profile"]["bullets"], list)
    # evidence ledger is driven by the candidate source of truth (24 claims)
    assert len(job["evidence"]) == 24


def test_approve_transitions_and_tracks_state(control):
    jid = control.post("/api/discover-demo").json()["first_execution_id"]
    approved = control.post(f"/api/jobs/{jid}/approve").json()["execution"]
    assert approved["status"] == "APPROVED"
    assert approved["approval"]["approved"] is True

    executions = control.get("/api/executions").json()
    assert executions["count"] == 1
    assert executions["executions"][0]["status"] == "APPROVED"

    history = control.get("/api/history").json()
    assert history["count"] >= 8
    activity = control.get("/api/activity").json()
    assert activity["count"] >= 8

    # cannot approve twice
    r = control.post(f"/api/jobs/{jid}/approve")
    assert r.status_code == 409


def test_withdraw(control):
    jid = control.post("/api/discover-demo").json()["first_execution_id"]
    w = control.post(f"/api/jobs/{jid}/withdraw").json()["execution"]
    assert w["status"] == "WITHDRAWN"


def test_unknown_job_404(control):
    assert control.get("/api/jobs/nope").status_code == 404
    assert control.post("/api/jobs/nope/approve").status_code == 404


def test_providers_and_candidate_and_base_resume(control):
    providers = control.get("/api/providers").json()["health"]
    assert "offline" in providers
    assert providers["offline"]["available"] is True

    cand = control.get("/api/candidate").json()["candidate"]
    assert cand["candidate"]["name"] == "Subrat Rout"

    resume = control.get("/api/base-resume").json()
    assert resume["summary"]
    assert len(resume["bullets"]) == 24
    assert resume["bullets"][0]["claim_id"].startswith("exp-0")


def test_interview_generates_questions_from_jd_and_evidence(control):
    control.post("/api/discover-demo")
    data = control.get("/api/interview").json()
    assert data["target_role"] == "Support Engineer"
    assert len(data["questions"]) > 0
    assert all(q["text"] for q in data["questions"])


def test_learning_plan_from_gaps(control):
    data = control.get("/api/learning").json()
    # With empty/tailored state the plan is still well-formed and non-failing.
    assert "source_gaps" in data
    assert "objectives" in data
    assert isinstance(data["objectives"], list)


def test_graph_contains_real_entities_and_relations(control):
    control.post("/api/discover-demo")
    g = control.get("/api/graph").json()
    nodes = g["nodes"]
    kinds = {n["kind"] for n in nodes}
    assert "candidate" in kinds
    assert "job" in kinds
    assert "company" in kinds
    job_node = next(n for n in nodes if n["kind"] == "job")
    assert job_node["company"] == "Acme"
    assert g["edges"]
