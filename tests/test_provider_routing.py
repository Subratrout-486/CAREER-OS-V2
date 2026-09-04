"""Tests for the provider routing / fallback health architecture.

These are pure-logic tests: no credentials are fabricated, no live provider is
queried, and the deterministic offline adapter is treated as the always-available
fallback so the pipeline remains operational without any LLM provider.
"""

from __future__ import annotations

import pytest

from career_os.providers.routing import (
    HTTPProviderAdapter,
    ModelRouter,
    OfflineAdapter,
    OllamaAdapter,
    ProviderAdapter,
    ProviderHealth,
    classify_provider_health,
)


class FakeHealthy(ProviderAdapter):
    provider = "http"

    def available(self) -> bool:
        return True

    def health(self) -> ProviderHealth:
        return ProviderHealth.AVAILABLE


class FakeOutage(ProviderAdapter):
    provider = "fake-outage"

    def available(self) -> bool:
        return False

    def health(self) -> ProviderHealth:
        return ProviderHealth.OUTAGE


class FakeBlocked(ProviderAdapter):
    provider = "fake-blocked"
    env_key = "CAREER_OS_FAKE_KEY"

    def __init__(self) -> None:
        super().__init__()
        self.api_key = ""

    def available(self) -> bool:
        return bool(self.api_key)


def test_health_enum_covers_all_contract_states():
    expected = {
        "AVAILABLE",
        "DEGRADED",
        "QUOTA_EXCEEDED",
        "RATE_LIMITED",
        "OUTAGE",
        "NOT_CONFIGURED",
        "PROVIDER_BLOCKED",
    }
    assert {s.value for s in ProviderHealth} == expected


@pytest.mark.parametrize(
    "message,expected",
    [
        ("You exceeded your current quota, please check billing", ProviderHealth.QUOTA_EXCEEDED),
        ("HTTP 429 too many requests", ProviderHealth.RATE_LIMITED),
        ("503 service unavailable", ProviderHealth.OUTAGE),
        ("502 bad gateway upstream", ProviderHealth.OUTAGE),
        ("request timed out after 60s", ProviderHealth.DEGRADED),
        ("unexpected parser error", ProviderHealth.DEGRADED),
    ],
)
def test_classify_provider_health(message, expected):
    assert classify_provider_health(message) is expected


def test_router_prefers_real_provider_over_offline():
    router = ModelRouter(adapters=[OfflineAdapter(), FakeHealthy()])
    route = router.route("classification")
    assert route.provider == "http"
    assert route.health is ProviderHealth.AVAILABLE


def test_router_falls_back_to_offline_when_all_unnavailable():
    router = ModelRouter(adapters=[OfflineAdapter(), FakeOutage()])
    route = router.route("classification")
    assert route.provider == "offline"
    assert route.health is ProviderHealth.AVAILABLE


def test_router_falls_back_when_ollama_is_outage(monkeypatch):
    # Ollama with an unreachable base URL reports OUTAGE and is skipped.
    adapter = OllamaAdapter(base_url="http://127.0.0.1:1")
    router = ModelRouter(adapters=[OfflineAdapter(), adapter])
    route = router.route("classification")
    assert route.provider == "offline"


def test_router_never_returns_blocked_or_not_configured_route():
    router = ModelRouter(adapters=[OfflineAdapter(), HTTPProviderAdapter()])
    assert HTTPProviderAdapter().available() is False
    route = router.route("classification")
    assert route.provider == "offline"
    assert route.health in {ProviderHealth.AVAILABLE, ProviderHealth.DEGRADED}


def test_router_health_reports_status_and_available():
    router = ModelRouter(adapters=[OfflineAdapter(), FakeBlocked()])
    health = router.health()
    assert health["offline"]["available"] is True
    assert health["offline"]["status"] == "AVAILABLE"
    # FakeBlocked without env key is not configured / blocked, not available.
    assert health["fake-blocked"]["available"] is False
    assert health["fake-blocked"]["status"] in {
        ProviderHealth.NOT_CONFIGURED.value,
        ProviderHealth.PROVIDER_BLOCKED.value,
    }


def test_record_failure_classifies_and_cooldowns():
    router = ModelRouter()
    router.record_failure("ollama", "You exceeded your quota for the free tier")
    assert router.failures["ollama"] == ["You exceeded your quota for the free tier"]
    assert router._cooldowns["ollama"] is ProviderHealth.QUOTA_EXCEEDED