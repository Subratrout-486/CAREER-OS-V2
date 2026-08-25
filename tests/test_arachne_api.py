from fastapi.testclient import TestClient

from career_os.arachne_api import create_arachne_router


def test_arachne_router_exposes_health_and_jobs(monkeypatch, tmp_path):
    monkeypatch.setenv("CAREER_OS_CONDUCTOR_TOKEN", "test-token")
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(create_arachne_router())
    client = TestClient(app)

    health = client.get("/api/v1/health", headers={"X-Career-OS-Token": "test-token"})
    assert health.status_code == 200
    assert health.json()["client"] == "arachne"
    assert health.json()["submission_enabled"] is False


def test_arachne_health_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("CAREER_OS_CONDUCTOR_TOKEN", "test-token")
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(create_arachne_router())
    client = TestClient(app)
    assert client.get("/api/v1/health").status_code == 401
