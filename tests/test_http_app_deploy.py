"""Deployment-contract tests for the ARACHNE HTTP application.

These lock in what a public deployment must guarantee: the ARACHNE dashboard is
served from the production app at "/", a token-free /healthz readiness probe
reports the persistent-storage roots, and every dashboard view's backing
control-plane endpoint responds.
"""

from fastapi.testclient import TestClient

from career_os.http_app import app

client = TestClient(app)

_DASHBOARD_ENDPOINTS = [
    "/api/overview",
    "/api/jobs",
    "/api/providers",
    "/api/graph",
    "/api/activity",
    "/api/history",
    "/api/approval-queue",
    "/api/executions",
    "/api/interview",
    "/api/learning",
]


def test_root_serves_the_arachne_dashboard() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "ARACHNE" in body
    for marker in (
        "Overview",
        "Job Discovery",
        "Approval Queue",
        "Workflow History",
        "Interview Prep",
        "Learning",
    ):
        assert marker in body


def test_healthz_is_reachable_without_a_token() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["ready"] is True
    assert payload["service"] == "career-os-v2"


def test_dashboard_backing_endpoints_respond() -> None:
    for path in _DASHBOARD_ENDPOINTS:
        response = client.get(path)
        assert response.status_code == 200, f"{path} -> {response.status_code}"
