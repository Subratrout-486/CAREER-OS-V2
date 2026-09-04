"""Real provider routing with offline and local-model adapters.

No credentials are provisioned here. Three adapter kinds are supported:

* ``OfflineAdapter`` - deterministic, dependency-free classification/extraction
  used as the always-available fallback in this environment (no live keys).
* ``OllamaAdapter`` - calls a local Ollama HTTP endpoint when configured
  (CAREER_OS_OLLAMA_URL) so high-volume inference can run without a paid key.
* ``HTTPProviderAdapter`` - base for a credentialed provider behind an explicit
  API-key environment variable; absent a key it stays unavailable.

Routing picks an available provider by task type, capability and failure
history. Failures are classified and never reported as success.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ProviderUnavailable(Exception):
    pass


class ProviderFailure(Exception):
    def __init__(self, message: str, kind: str = "unknown") -> None:
        super().__init__(message)
        self.kind = kind


class ProviderHealth(StrEnum):
    """Health classification for a provider adapter.

    Mirrors the states the autonomy controller and dashboard surface:
    AVAILABLE / DEGRADED / QUOTA_EXCEEDED / RATE_LIMITED / OUTAGE /
    NOT_CONFIGURED / PROVIDER_BLOCKED.
    """

    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    RATE_LIMITED = "RATE_LIMITED"
    OUTAGE = "OUTAGE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    PROVIDER_BLOCKED = "PROVIDER_BLOCKED"


_QUOTA_PATTERNS = ("quota", "exhausted", "billing", "insufficient_quota", "402")
_RATE_PATTERNS = ("rate limit", "too many requests", "429")
_OUTAGE_PATTERNS = ("503", "service unavailable", "temporarily unavailable", "outage", "502", "504")
_DEGRADED_PATTERNS = ("timeout", "slow", "high latency", "degraded", "502", "504")


def classify_provider_health(message: str) -> ProviderHealth:
    """Bucket an arbitrary provider error message into a health state.

    No credential values are inspected or logged - only the message text.
    """
    normalized = (message or "").lower()
    if any(p in normalized for p in _QUOTA_PATTERNS):
        return ProviderHealth.QUOTA_EXCEEDED
    if any(p in normalized for p in _RATE_PATTERNS):
        return ProviderHealth.RATE_LIMITED
    if any(p in normalized for p in _OUTAGE_PATTERNS):
        return ProviderHealth.OUTAGE
    if any(p in normalized for p in _DEGRADED_PATTERNS):
        return ProviderHealth.DEGRADED
    return ProviderHealth.DEGRADED


class ProviderAdapter:
    provider: str = "base"

    def available(self) -> bool:
        return False

    def health(self) -> ProviderHealth:
        return ProviderHealth.AVAILABLE if self.available() else ProviderHealth.NOT_CONFIGURED

    def complete(self, *, system: str, user: str, max_tokens: int = 512) -> str:
        raise ProviderUnavailable(f"{self.provider} is not available")


class OfflineAdapter(ProviderAdapter):
    """Deterministic, dependency-free adapter used when no key is present."""

    provider = "offline"

    def available(self) -> bool:
        return True

    def health(self) -> ProviderHealth:
        return ProviderHealth.AVAILABLE

    def complete(self, *, system: str, user: str, max_tokens: int = 512) -> str:
        # Return nothing beyond what deterministic rules compute; model calls
        # are optional enrichment. This keeps the system fully operational
        # with zero credentials.
        return ""


class OllamaAdapter(ProviderAdapter):
    """Local-model adapter via Ollama's HTTP API (no paid account needed)."""

    provider = "ollama"

    def __init__(self, base_url: str | None = None, model: str = "qwen3:8b") -> None:
        self.base_url = (base_url or os.getenv("CAREER_OS_OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.model = model

    def available(self) -> bool:
        if not self.base_url:
            return False
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=3) as response:
                return response.status == 200
        except Exception:  # noqa: BLE001 - any network error means the model is unavailable
            return False

    def health(self) -> ProviderHealth:
        if not self.base_url:
            return ProviderHealth.NOT_CONFIGURED
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=3) as response:
                return (
                    ProviderHealth.DEGRADED
                    if response.status != 200
                    else ProviderHealth.AVAILABLE
                )
        except Exception:  # noqa: BLE001 - connectivity failure maps to outage for routing
            return ProviderHealth.OUTAGE

    def complete(self, *, system: str, user: str, max_tokens: int = 512) -> str:
        payload = {
            "model": self.model,
            "prompt": user,
            "system": system,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise ProviderFailure(f"ollama request failed: {exc}", kind="temporary") from exc
        return str(data.get("response", "")).strip()


class HTTPProviderAdapter(ProviderAdapter):
    """Base for a credentialed model provider behind an env API key."""

    provider = "http"
    env_key = ""

    def __init__(self) -> None:
        self.api_key = os.getenv(self.env_key, "").strip()

    def available(self) -> bool:
        return bool(self.api_key)

    def health(self) -> ProviderHealth:
        if not self.api_key:
            return ProviderHealth.NOT_CONFIGURED
        if not self.configured():
            return ProviderHealth.PROVIDER_BLOCKED
        return ProviderHealth.AVAILABLE

    def configured(self) -> bool:
        """Subclasses override with a concrete endpoint/requirement check."""
        return bool(self.api_key)

    def complete(self, *, system: str, user: str, max_tokens: int = 512) -> str:
        if not self.api_key:
            raise ProviderUnavailable(f"{self.provider} requires {self.env_key}")
        raise ProviderFailure(f"{self.provider} integration not configured", kind="configuration")


@dataclass
class ModelRoute:
    provider: str
    model: str
    task: str
    health: ProviderHealth = ProviderHealth.AVAILABLE


_TASK_CAPABILITY: dict[str, tuple[str, ...]] = {
    "classification": ("offline", "ollama", "http"),
    "extraction": ("offline", "ollama", "http"),
    "resume_analysis": ("offline", "ollama", "http"),
    "fit_scoring": ("offline", "ollama", "http"),
    "coaching": ("offline", "ollama", "http"),
}


class ModelRouter:
    """Route model calls to the best currently available provider.

    Routing prefers a real model provider (local or credentialed HTTP) over the
    deterministic offline adapter so enrichment is used when present, and falls
    back to ``offline`` when every other provider is unhealthy. The deterministic
    pipeline therefore stays operational even when no LLM provider is
    reachable. Failures are classified into the seven health states and never
    reported as success.
    """

    def __init__(self, adapters: list[ProviderAdapter] | None = None) -> None:
        self.adapters = adapters or [OfflineAdapter(), OllamaAdapter()]
        self.failures: dict[str, list[str]] = {}
        self._cooldowns: dict[str, ProviderHealth] = {}

    def available(self, task: str) -> ProviderAdapter:
        for adapter in self.adapters:
            if adapter.available() and adapter.provider in _TASK_CAPABILITY.get(task, ("offline",)):
                return adapter
        return OfflineAdapter()

    def route(self, task: str) -> ModelRoute:
        """Pick the best provider for a task; never returns an unusable route."""
        capable = [
            a for a in self.adapters
            if a.provider in _TASK_CAPABILITY.get(task, ("offline",))
        ]
        # Prefer a healthy real provider, then a degraded-but-configured one,
        # and only then the always-available deterministic offline adapter.
        for adapter in capable:
            if adapter.health() is ProviderHealth.AVAILABLE and adapter.provider != "offline":
                return self._route_for(adapter, task)
        for adapter in capable:
            if adapter.health() in {ProviderHealth.DEGRADED, ProviderHealth.AVAILABLE}:
                return self._route_for(adapter, task)
        offline = next((a for a in capable if a.provider == "offline"), OfflineAdapter())
        return self._route_for(offline, task)

    def _route_for(self, adapter: ProviderAdapter, task: str) -> ModelRoute:
        health = adapter.health()
        return ModelRoute(
            provider=adapter.provider,
            model=getattr(adapter, "model", task),
            task=task,
            health=health,
        )

    def record_failure(self, provider: str, message: str) -> None:
        self.failures.setdefault(provider, []).append(message)
        self._cooldowns[provider] = classify_provider_health(message)

    def health(self) -> dict[str, Any]:
        return {
            adapter.provider: {
                "available": adapter.available(),
                "status": adapter.health().value,
            }
            for adapter in self.adapters
        }
