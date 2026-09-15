from career_os.agentflow_client import AgentFlowClient, AgentFlowConfig, AgentFlowError


def test_agentflow_is_disabled_without_token():
    config = AgentFlowConfig(base_url="http://agentflow.test", token="")
    assert not config.enabled
    try:
        AgentFlowClient(config).submit_objective("test")
    except AgentFlowError as exc:
        assert "not configured" in str(exc)
    else:
        raise AssertionError("disabled AgentFlow client must fail closed")


def test_agentflow_config_reads_environment(monkeypatch):
    monkeypatch.setenv("CAREER_OS_AGENTFLOW_URL", "https://agentflow.example")
    monkeypatch.setenv("CAREER_OS_AGENTFLOW_TOKEN", "secret")
    monkeypatch.setenv("CAREER_OS_AGENTFLOW_TIMEOUT_SECONDS", "12")
    config = AgentFlowConfig.from_env()
    assert config.base_url == "https://agentflow.example"
    assert config.token == "secret"
    assert config.timeout_seconds == 12.0
    assert config.enabled
