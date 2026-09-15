"""Small, provider-agnostic client for delegated AI work through AgentFlow Studio.

Career OS V2 keeps its deterministic pipeline intact. This client is an explicit
boundary for optional model work; it never submits applications or executes
browser controls.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class AgentFlowConfig:
    base_url: str
    token: str
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "AgentFlowConfig":
        return cls(
            base_url=os.getenv("CAREER_OS_AGENTFLOW_URL", "http://127.0.0.1:3000").rstrip("/"),
            token=os.getenv("CAREER_OS_AGENTFLOW_TOKEN", "").strip(),
            timeout_seconds=float(os.getenv("CAREER_OS_AGENTFLOW_TIMEOUT_SECONDS", "60")),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.token)


class AgentFlowError(RuntimeError):
    """Raised when AgentFlow cannot accept or complete delegated work."""


class AgentFlowClient:
    def __init__(self, config: AgentFlowConfig | None = None):
        self.config = config or AgentFlowConfig.from_env()

    def submit_objective(
        self,
        objective: str,
        *,
        workflow: str = "CAREER OS V2",
        provider: str = "auto",
        nodes: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not self.config.enabled:
            raise AgentFlowError("AgentFlow is not configured; set CAREER_OS_AGENTFLOW_TOKEN")
        payload: dict[str, Any] = {
            "objective": objective,
            "workflow": workflow,
            "provider": provider,
        }
        if nodes:
            payload["nodes"] = nodes
        try:
            response = httpx.post(
                f"{self.config.base_url}/api/conductor/v1/bridge/objectives",
                json=payload,
                headers={"Authorization": f"Bearer {self.config.token}"},
                timeout=self.config.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AgentFlowError(f"AgentFlow request failed: {exc}") from exc
        if response.status_code != 202:
            raise AgentFlowError(f"AgentFlow rejected objective ({response.status_code})")
        return response.json()

    def get_run(self, run_id: str) -> dict[str, Any]:
        if not self.config.enabled:
            raise AgentFlowError("AgentFlow is not configured; set CAREER_OS_AGENTFLOW_TOKEN")
        try:
            response = httpx.get(
                f"{self.config.base_url}/api/conductor/v1/bridge/runs/{run_id}",
                headers={"Authorization": f"Bearer {self.config.token}"},
                timeout=self.config.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AgentFlowError(f"AgentFlow request failed: {exc}") from exc
        if response.status_code != 200:
            raise AgentFlowError(f"AgentFlow run lookup failed ({response.status_code})")
        return response.json()
