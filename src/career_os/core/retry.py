from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 8.0
    jitter: float = 0.2

    def delay(self, attempt: int, retry_after: float | None = None) -> float:
        if retry_after is not None:
            return min(max(0.0, retry_after), self.max_delay)
        raw = min(self.max_delay, self.base_delay * (2 ** max(0, attempt - 1)))
        return raw * (1 + random.uniform(-self.jitter, self.jitter))


def retry_call(
    fn: Callable[[], object],
    *,
    policy: RetryPolicy | None = None,
    retryable: Callable[[Exception], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[object, int]:
    selected = policy or RetryPolicy()
    should_retry = retryable or (lambda exc: isinstance(exc, (TimeoutError, ConnectionError)))
    attempt = 1
    while True:
        try:
            return fn(), attempt
        except Exception as exc:
            if attempt >= selected.max_attempts or not should_retry(exc):
                raise
            sleep(selected.delay(attempt))
            attempt += 1
