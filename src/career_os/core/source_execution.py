from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import TypeVar

from career_os.core.retry import RetryPolicy, retry_call

T = TypeVar("T")


@dataclass(frozen=True)
class ExecutionResult:
    value: object
    attempts: int


def execute_bounded(
    tasks: list[tuple[str, Callable[[], T]]],
    *,
    max_workers: int = 4,
    retry_policy: RetryPolicy | None = None,
    retryable: Callable[[Exception], bool] | None = None,
) -> dict[str, ExecutionResult | Exception]:
    """Execute independent source tasks with bounded concurrency and retries."""
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")

    results: dict[str, ExecutionResult | Exception] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(retry_call, task, policy=retry_policy, retryable=retryable): name
            for name, task in tasks
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                value, attempts = future.result()
                results[name] = ExecutionResult(value=value, attempts=attempts)
            except Exception as exc:
                results[name] = exc
    return results
