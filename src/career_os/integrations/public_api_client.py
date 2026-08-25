from __future__ import annotations

import json
from time import sleep
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


JsonValue = dict[str, Any] | list[Any]


class PublicAPIError(RuntimeError):
    """A public-provider request failed after bounded retries."""


class PublicAPIClient:
    """Dependency-free JSON client with bounded retries and timeouts."""

    RETRYABLE_HTTP = frozenset({408, 425, 429, 500, 502, 503, 504})

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        retries: int = 2,
        backoff_seconds: float = 0.5,
        opener: Callable[..., Any] | None = None,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        if timeout <= 0 or retries < 0 or backoff_seconds < 0:
            raise ValueError("invalid HTTP client settings")
        self.timeout = timeout
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self.opener = opener or urlopen
        self.sleeper = sleeper

    def get_json(self, url: str, *, headers: dict[str, str] | None = None) -> JsonValue:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Career-OS-V2/0.1",
                **(headers or {}),
            },
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    status = getattr(response, "status", 200)
                    if not 200 <= status < 300:
                        raise PublicAPIError(f"HTTP {status}")
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                last_error = exc
                if exc.code not in self.RETRYABLE_HTTP:
                    raise PublicAPIError(f"HTTP {exc.code}") from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                delay = self._delay(attempt, retry_after)
            except (URLError, TimeoutError, json.JSONDecodeError, PublicAPIError) as exc:
                last_error = exc
                delay = self._delay(attempt, None)
            if attempt < self.retries:
                self.sleeper(delay)
        raise PublicAPIError("request failed after bounded retries") from last_error

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(30.0, max(0.0, float(retry_after)))
            except ValueError:
                pass
        return min(8.0, self.backoff_seconds * (2**attempt))
