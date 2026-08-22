from __future__ import annotations

from collections import defaultdict
from threading import Lock, Semaphore


class ServiceLimiter:
    """Bound concurrent work per shared service while allowing unrelated services to run."""

    def __init__(self, limits: dict[str, int] | None = None, default_limit: int | None = None) -> None:
        self._limits = dict(limits or {})
        self._default_limit = default_limit
        self._semaphores: dict[str, Semaphore] = {}
        self._lock = Lock()

    def _limit_for(self, service: str) -> int | None:
        return self._limits.get(service, self._default_limit)

    def _semaphore_for(self, service: str) -> Semaphore | None:
        limit = self._limit_for(service)
        if limit is None:
            return None
        if limit < 1:
            raise ValueError("service limits must be >= 1")
        with self._lock:
            return self._semaphores.setdefault(service, Semaphore(limit))

    def run(self, service: str, fn):
        semaphore = self._semaphore_for(service)
        if semaphore is None:
            return fn()
        with semaphore:
            return fn()

    def active_service_count(self) -> int:
        with self._lock:
            return len(self._semaphores)
