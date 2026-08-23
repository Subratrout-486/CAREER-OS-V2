"""Provider-neutral control plane for the Career OS autonomous loop.

The controller owns durable progress and provider selection. Provider adapters are
kept outside this module so an adapter can never merge a PR or bypass CI on its own.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import json
from pathlib import Path
import tempfile
from typing import Iterable


class ProviderFailureKind(StrEnum):
    QUOTA = "quota"
    RATE_LIMIT = "rate_limit"
    TEMPORARY = "temporary"
    OUTAGE = "outage"
    MODEL_UNAVAILABLE = "model_unavailable"
    AUTHORIZATION = "authorization"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


class ControllerStatus(StrEnum):
    READY = "ready"
    PROVIDER_BLOCKED = "provider_blocked"
    HUMAN_REQUIRED = "human_required"


@dataclass
class DepartmentState:
    department: str
    phase: str = "research"
    provider: str | None = None
    attempts: int = 0
    provider_failures: dict[str, list[str]] = field(default_factory=dict)
    failure_metadata: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    last_error: str | None = None
    status: ControllerStatus = ControllerStatus.READY


@dataclass
class ControllerState:
    current_department: str
    departments: list[str]
    completed_departments: list[str] = field(default_factory=list)
    department_state: DepartmentState | None = None


@dataclass(frozen=True)
class ProviderFailure:
    provider: str
    kind: ProviderFailureKind
    message: str
    model: str | None = None
    timestamp: str | None = None
    retry_after: str | None = None


@dataclass(frozen=True)
class ProviderBlockedHandoff:
    status: str
    department: str
    attempted_providers: tuple[str, ...]
    last_failure: str
    next_action: str
    failure_kind: str | None = None
    provider: str | None = None
    model: str | None = None
    retry_after: str | None = None


_FAILURE_PATTERNS: tuple[tuple[ProviderFailureKind, tuple[str, ...]], ...] = (
    (ProviderFailureKind.QUOTA, ("quota", "exhausted", "billing details")),
    (ProviderFailureKind.RATE_LIMIT, ("rate limit", "too many requests", "429")),
    (ProviderFailureKind.MODEL_UNAVAILABLE, ("model unavailable", "model_not_found", "model not found")),
    (ProviderFailureKind.OUTAGE, ("service unavailable", "temporarily unavailable", "outage", "503")),
    (ProviderFailureKind.AUTHORIZATION, ("unauthorized", "forbidden", "invalid api key", "401", "403")),
    (ProviderFailureKind.CONFIGURATION, ("invalid configuration", "configuration error", "unsupported argument", "unknown arguments")),
    (ProviderFailureKind.TEMPORARY, ("timeout", "connection reset", "temporary", "502", "504")),
)

_RETRY_DELAYS = {
    ProviderFailureKind.QUOTA: timedelta(hours=24),
    ProviderFailureKind.RATE_LIMIT: timedelta(minutes=15),
    ProviderFailureKind.TEMPORARY: timedelta(minutes=10),
    ProviderFailureKind.OUTAGE: timedelta(minutes=30),
    ProviderFailureKind.MODEL_UNAVAILABLE: timedelta(hours=1),
}


def classify_provider_failure(message: str) -> ProviderFailureKind:
    """Classify a provider error without inspecting or logging credential values."""
    normalized = message.lower()
    for kind, patterns in _FAILURE_PATTERNS:
        if any(pattern in normalized for pattern in patterns):
            return kind
    return ProviderFailureKind.UNKNOWN


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _retry_at(kind: ProviderFailureKind, timestamp: datetime) -> str | None:
    delay = _RETRY_DELAYS.get(kind)
    return (timestamp + delay).isoformat().replace("+00:00", "Z") if delay else None


class ProviderController:
    """Durable scheduler for one department and already-authorized providers."""

    def __init__(self, state_path: Path, providers: Iterable[str]):
        self.state_path = state_path
        self.providers = tuple(dict.fromkeys(providers))
        self.state = self._load()

    def start(self, departments: Iterable[str]) -> DepartmentState:
        names = list(dict.fromkeys(departments))
        if not names:
            raise ValueError("at least one department is required")
        if self.state is None:
            self.state = ControllerState(current_department=names[0], departments=names)
        elif self.state.departments != names:
            raise ValueError("department list cannot change for an existing run")
        if self.state.department_state is None:
            self.state.department_state = DepartmentState(self.state.current_department)
        self._save()
        return self.state.department_state

    def choose_provider(self, now: datetime | None = None) -> str | None:
        if self.state is None or self.state.department_state is None:
            raise RuntimeError("call start() before choosing a provider")
        current = self.state.department_state
        instant = now or _utc_now()
        for provider in self.providers:
            metadata = current.failure_metadata.get(provider, [])
            if metadata:
                retry_at = _parse_timestamp(metadata[-1].get("retry_after"))
                if retry_at is None or instant < retry_at:
                    continue
            elif provider in current.provider_failures:
                # Legacy state has no retry metadata; do not spin on it automatically.
                continue
            current.provider = provider
            current.status = ControllerStatus.READY
            self._save()
            return provider
        current.provider = None
        current.status = ControllerStatus.PROVIDER_BLOCKED
        self._save()
        return None

    def record_provider_failure(self, failure: ProviderFailure) -> str | None:
        if self.state is None or self.state.department_state is None:
            raise RuntimeError("call start() before recording a failure")
        if failure.provider not in self.providers:
            raise ValueError("failure provider is not configured")
        current = self.state.department_state
        current.attempts += 1
        current.last_error = failure.message
        current.provider_failures.setdefault(failure.provider, []).append(failure.kind.value)
        observed_at = _parse_timestamp(failure.timestamp) or _utc_now()
        retry_after = failure.retry_after or _retry_at(failure.kind, observed_at)
        current.failure_metadata.setdefault(failure.provider, []).append(
            {
                "kind": failure.kind.value,
                "model": failure.model,
                "timestamp": observed_at.isoformat().replace("+00:00", "Z"),
                "retry_after": retry_after,
            }
        )
        current.provider = None
        next_provider = self.choose_provider(now=observed_at)
        if next_provider is None:
            current.status = ControllerStatus.PROVIDER_BLOCKED
        self._save()
        return next_provider

    def provider_blocked_handoff(self) -> ProviderBlockedHandoff | None:
        if self.state is None or self.state.department_state is None:
            return None
        current = self.state.department_state
        if current.status is not ControllerStatus.PROVIDER_BLOCKED:
            return None
        provider = None
        kind = None
        model = None
        retry_after = None
        if current.failure_metadata:
            provider = next(reversed(current.failure_metadata))
            latest = current.failure_metadata[provider][-1]
            kind = latest.get("kind")
            model = latest.get("model")
            retry_after = latest.get("retry_after")
        return ProviderBlockedHandoff(
            status=ControllerStatus.PROVIDER_BLOCKED.value,
            department=current.department,
            attempted_providers=tuple(current.provider_failures),
            last_failure=current.last_error or "provider failure without message",
            next_action="Authorize another provider or restore an existing provider quota; no credential is created automatically.",
            failure_kind=kind,
            provider=provider,
            model=model,
            retry_after=retry_after,
        )

    def advance_department(self) -> DepartmentState | None:
        if self.state is None or self.state.department_state is None:
            raise RuntimeError("call start() before advancing")
        current = self.state.department_state
        if current.status is not ControllerStatus.READY or current.phase != "ready_to_merge":
            raise ValueError("department is not verified and ready to merge")
        index = self.state.departments.index(current.department)
        if current.department not in self.state.completed_departments:
            self.state.completed_departments.append(current.department)
        if index + 1 >= len(self.state.departments):
            self._save()
            return None
        self.state.current_department = self.state.departments[index + 1]
        self.state.department_state = DepartmentState(self.state.current_department)
        self._save()
        return self.state.department_state

    def mark_ready_to_merge(self) -> None:
        if self.state is None or self.state.department_state is None:
            raise RuntimeError("call start() before marking readiness")
        current = self.state.department_state
        if not current.provider:
            raise ValueError("a provider must be selected")
        current.phase = "ready_to_merge"
        self._save()

    def _load(self) -> ControllerState | None:
        if not self.state_path.exists():
            return None
        raw = json.loads(self.state_path.read_text())
        department = raw.get("department_state")
        if department:
            department.setdefault("failure_metadata", {})
        return ControllerState(
            current_department=raw["current_department"],
            departments=list(raw["departments"]),
            completed_departments=list(raw.get("completed_departments", [])),
            department_state=DepartmentState(**department) if department else None,
        )

    def _save(self) -> None:
        if self.state is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(self.state), indent=2, sort_keys=True) + "\n"
        with tempfile.NamedTemporaryFile("w", dir=self.state_path.parent, delete=False) as handle:
            handle.write(payload)
            temp_name = handle.name
        Path(temp_name).replace(self.state_path)
