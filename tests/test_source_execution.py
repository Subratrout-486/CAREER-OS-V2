from career_os.core.retry import RetryPolicy
from career_os.core.source_execution import ExecutionResult, execute_bounded


def test_bounded_execution_retries_transient_failure_and_preserves_result():
    calls = {"a": 0}
    sleeps: list[float] = []

    def flaky():
        calls["a"] += 1
        if calls["a"] == 1:
            raise TimeoutError("temporary")
        return "ok"

    # Inject a zero-sleep policy by using the retry primitive directly through a
    # deterministic retry policy; the execution helper remains network-agnostic.
    result = execute_bounded(
        [("a", flaky)],
        max_workers=1,
        retry_policy=RetryPolicy(max_attempts=2, base_delay=0, max_delay=0, jitter=0),
    )
    assert isinstance(result["a"], ExecutionResult)
    assert result["a"].value == "ok"
    assert result["a"].attempts == 2
    assert calls["a"] == 2


def test_bounded_execution_isolates_per_task_failures():
    def broken():
        raise RuntimeError("broken source")

    result = execute_bounded(
        [("broken", broken), ("healthy", lambda: [1, 2, 3])],
        max_workers=2,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    assert isinstance(result["broken"], RuntimeError)
    assert isinstance(result["healthy"], ExecutionResult)
    assert result["healthy"].value == [1, 2, 3]
