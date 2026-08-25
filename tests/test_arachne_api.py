from fastapi.testclient import TestClient

import career_os.arachne_api as arachne_api


def app_for_test(monkeypatch):
    monkeypatch.setenv("CAREER_OS_CONDUCTOR_TOKEN", "test-token")
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(arachne_api.create_arachne_router())
    return TestClient(app)


def test_health_requires_token(monkeypatch):
    client = app_for_test(monkeypatch)
    assert client.get("/api/v1/health").status_code == 401
    response = client.get("/api/v1/health", headers={"X-Career-OS-Token": "test-token"})
    assert response.status_code == 200
    assert response.json()["client"] == "arachne"
    assert response.json()["submission_enabled"] is False


def test_job_enters_automatic_processor(monkeypatch):
    calls = []

    class FakeProcessor:
        def process(self, request):
            calls.append(request.job)
            return object()

    monkeypatch.setattr(arachne_api, "AutomaticJobProcessor", FakeProcessor)
    monkeypatch.setattr(arachne_api, "result_to_dict", lambda result: {"tailored_resume": {"summary": "ready"}})
    client = app_for_test(monkeypatch)
    response = client.post(
        "/api/v1/jobs",
        headers={"X-Career-OS-Token": "test-token"},
        json={"idempotency_key": "arachne-test-001", "job": {"company": "Example", "title": "Support Engineer", "url": "https://example.com/job/1", "description": "SQL support"}},
    )
    assert response.status_code == 200
    assert response.json()["processing"] == "automatic"
    assert response.json()["submission_enabled"] is False
    assert calls[0]["title"] == "Support Engineer"


def test_duplicate_idempotency_key_is_rejected(monkeypatch):
    monkeypatch.setattr(arachne_api, "AutomaticJobProcessor", lambda: type("P", (), {"process": lambda self, request: object()})())
    monkeypatch.setattr(arachne_api, "result_to_dict", lambda result: {})
    client = app_for_test(monkeypatch)
    payload = {"idempotency_key": "arachne-test-duplicate", "job": {"title": "Support Engineer"}}
    assert client.post("/api/v1/jobs", headers={"X-Career-OS-Token": "test-token"}, json=payload).status_code == 200
    assert client.post("/api/v1/jobs", headers={"X-Career-OS-Token": "test-token"}, json=payload).status_code == 409
