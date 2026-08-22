from career_os.core.retry import RetryPolicy
from career_os.core.service_limits import ServiceLimiter
from career_os.core.source_execution import ExecutionResult, execute_bounded


def test_same_service_is_limited_while_other_service_runs():
    import threading
    import time

    active = {"greenhouse": 0, "lever": 0}
    peak = {"greenhouse": 0, "lever": 0}
    lock = threading.Lock()

    def work(service):
        def run():
            with lock:
                active[service] += 1
                peak[service] = max(peak[service], active[service])
            time.sleep(0.02)
            with lock:
                active[service] -= 1
            return service
        return run

    tasks = [
        ("gh-1", work("greenhouse")),
        ("gh-2", work("greenhouse")),
        ("lever-1", work("lever")),
    ]
    result = execute_bounded(
        tasks,
        max_workers=3,
        retry_policy=RetryPolicy(max_attempts=1),
        service_limiter=ServiceLimiter({"greenhouse": 1, "lever": 2}),
        service_for=lambda name: "greenhouse" if name.startswith("gh-") else "lever",
    )
    assert all(isinstance(value, ExecutionResult) for value in result.values())
    assert peak["greenhouse"] == 1
    assert peak["lever"] == 1


def test_invalid_worker_count_is_rejected():
    try:
        execute_bounded([], max_workers=0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
