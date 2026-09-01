from __future__ import annotations

from career_os.application.jobpilot_executor import JobPilotExecutor


def test_jobpilot_executor_requires_runtime_configuration(monkeypatch):
    for name in ("JOBPILOT_API", "JOBPILOT_API_TOKEN", "JOBPILOT_TERMINAL_URL"):
        monkeypatch.delenv(name, raising=False)
    try:
        JobPilotExecutor()
    except RuntimeError as exc:
        assert "JOBPILOT_API" in str(exc)
    else:
        raise AssertionError("missing JobPilot runtime configuration was accepted")


def test_jobpilot_executor_builds_campaign_and_dispatches_browser(monkeypatch):
    calls = []
    executor = JobPilotExecutor(
        api_url="http://jobpilot/api", api_token="test-token", terminal_url="http://terminal", timeout=0, poll_interval=0
    )

    def request(method, path, body=None):
        calls.append(("api", method, path, body))
        if path.startswith("/api/applied/check"):
            return {"applied": False}
        if path == "/api/campaigns":
            return {"campaignId": "campaign-1"}
        if path == "/api/campaigns/campaign-1/jobs":
            return {"items": []}
        raise AssertionError(path)

    def terminal(path, body):
        calls.append(("terminal", path, body))
        return {}

    monkeypatch.setattr(executor, "_request", request)
    monkeypatch.setattr(executor, "_terminal", terminal)
    result = executor.execute(
        {"application_url": "https://example.com/apply", "title": "Engineer", "company": "Example"}, {}, "/tmp/resume.pdf"
    )

    assert result.submitted is False
    assert result.state == "timeout"
    assert any(kind == "terminal" and path == "/sessions/start" for kind, path, _ in calls)
    assert any(kind == "terminal" and path == "/sessions/inject" for kind, path, _ in calls)
    api_calls = [(method, path, body) for kind, method, path, body in calls if kind == "api"]
    assert any(path == "/api/campaigns" and body["source"] == "career-os" for _, path, body in api_calls)


def test_jobpilot_executor_refuses_duplicate_before_browser(monkeypatch):
    executor = JobPilotExecutor(
        api_url="http://jobpilot/api", api_token="test-token", terminal_url="http://terminal", timeout=1
    )

    monkeypatch.setattr(executor, "_request", lambda method, path, body=None: {"applied": True, "match": {"kind": "url"}})
    monkeypatch.setattr(executor, "_terminal", lambda *args: (_ for _ in ()).throw(AssertionError("browser must not start")))

    result = executor.execute(
        {"application_url": "https://example.com/apply", "title": "Engineer", "company": "Example"}, {}, "resume.pdf"
    )
    assert result.state == "duplicate"
    assert result.submitted is False
