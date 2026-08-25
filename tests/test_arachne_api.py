from pathlib import Path

from fastapi.testclient import TestClient

import career_os.arachne_api as arachne_api
from career_os.arachne_store import ArachneResultStore


def app_for_test(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CAREER_OS_CONDUCTOR_TOKEN", "test-token")
    store = ArachneResultStore(tmp_path / "arachne")
    monkeypatch.setattr(arachne_api, "ArachneResultStore", lambda: store)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(arachne_api.create_arachne_router())
    return TestClient(app)


def test_health_requires_token(monkeypatch, tmp_path):
    client = app_for_test(monkeypatch, tmp_path)
    assert client.get("/api/v1/health").status_code == 401
    response = client.get("/api/v1/health", headers={"X-Career-OS-Token": "test-token"})
    assert response.status_code == 200
    assert response.json()["client"] == "arachne"
    assert response.json()["submission_enabled"] is False


def test_job_enters_automatic_processor(monkeypatch, tmp_path):
    calls = []

    class FakeJob:
        canonical_key = "example:support-engineer:hyderabad:job-1"

    class FakeResult:
        job = FakeJob()

    class FakeProcessor:
        def process(self, request):
            calls.append(request.job)
            return FakeResult()

    monkeypatch.setattr(arachne_api, "AutomaticJobProcessor", FakeProcessor)
    monkeypatch.setattr(arachne_api, "result_to_dict", lambda result: {"job": {"canonical_key": result.job.canonical_key}, "tailored_resume": {"summary": "ready"}})
    client = app_for_test(monkeypatch, tmp_path)
    response = client.post("/api/v1/jobs", headers={"X-Career-OS-Token": "test-token"}, json={"idempotency_key": "arachne-test-001", "job": {"company": "Example", "title": "Support Engineer"}})
    assert response.status_code == 200
    assert response.json()["processing"] == "automatic"
    assert calls[0]["title"] == "Support Engineer"
    listed = client.get("/api/v1/jobs", headers={"X-Career-OS-Token": "test-token"})
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    fetched = client.get("/api/v1/jobs/example:support-engineer:hyderabad:job-1", headers={"X-Career-OS-Token": "test-token"})
    assert fetched.status_code == 200
    assert fetched.json()["tailored_resume"]["summary"] == "ready"


def test_duplicate_idempotency_key_is_rejected(monkeypatch, tmp_path):
    class FakeJob:
        canonical_key = "example:support-engineer:hyderabad:job-2"

    class FakeResult:
        job = FakeJob()

    monkeypatch.setattr(arachne_api, "AutomaticJobProcessor", lambda: type("P", (), {"process": lambda self, request: FakeResult()})())
    monkeypatch.setattr(arachne_api, "result_to_dict", lambda result: {"job": {"canonical_key": result.job.canonical_key}})
    client = app_for_test(monkeypatch, tmp_path)
    payload = {"idempotency_key": "arachne-test-duplicate", "job": {"title": "Support Engineer"}}
    assert client.post("/api/v1/jobs", headers={"X-Career-OS-Token": "test-token"}, json=payload).status_code == 200
    assert client.post("/api/v1/jobs", headers={"X-Career-OS-Token": "test-token"}, json=payload).status_code == 409
