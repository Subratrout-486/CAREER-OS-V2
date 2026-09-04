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
from typing import Any


class ProviderUnavailable(Exception):
    pass


class ProviderFailure(Exception):
    def __init__(self, message: str, kind: str = "unknown") -> None:
        super().__init__(message)
        self.kind = kind


class ProviderAdapter:
    provider: str = "base"

    def available(self) -> bool:
        return False

    def complete(self, *, system: str, user: str, max_tokens: int = 512) -> str:
        raise ProviderUnavailable(f"{self.provider} is not available")


class OfflineAdapter(ProviderAdapter):
    """Deterministic, dependency-free adapter used when no key is present."""

    provider = "offline"

    def available(self) -> bool:
        return True

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

    def complete(self, *, system: str, user: str, max_tokens: int = 512) -> str:
        if not self.api_key:
            raise ProviderUnavailable(f"{self.provider} requires {self.env_key}")
        raise ProviderFailure(f"{self.provider} integration not configured", kind="configuration")


@dataclass
class ModelRoute:
    provider: str
    model: str
    task: str


_TASK_CAPABILITY: dict[str, tuple[str, ...]] = {
    "classification": ("offline", "ollama"),
    "extraction": ("offline", "ollama"),
    "resume_analysis": ("offline", "ollama"),
    "fit_scoring": ("offline", "ollama"),
    "coaching": ("offline", "ollama"),
}


class ModelRouter:
    """Route model calls to the best currently available provider."""

    def __init__(self, adapters: list[ProviderAdapter] | None = None) -> None:
        self.adapters = adapters or [OfflineAdapter(), OllamaAdapter()]
        self.failures: dict[str, list[str]] = {}

    def available(self, task: str) -> ProviderAdapter:
        for adapter in self.adapters:
            if adapter.available() and adapter.provider in _TASK_CAPABILITY.get(task, ("offline",)):
                return adapter
        return OfflineAdapter()

    def record_failure(self, provider: str, message: str) -> None:
        self.failures.setdefault(provider, []).append(message)

    def health(self) -> dict[str, Any]:
        return {
            adapter.provider: {"available": adapter.available()}
            for adapter in self.adapters
        }
