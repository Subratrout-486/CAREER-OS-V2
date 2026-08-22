from career_os.core.retry import RetryPolicy, retry_call


def test_retry_uses_exponential_backoff_and_stops_after_success():
    attempts = 0
    sleeps: list[float] = []

    def work():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TimeoutError("temporary")
        return "ok"

    result, used = retry_call(work, policy=RetryPolicy(max_attempts=3, base_delay=1, jitter=0), sleep=sleeps.append)
    assert result == "ok"
    assert used == 3
    assert sleeps == [1, 2]


def test_retry_does_not_retry_non_retryable_errors():
    attempts = 0

    def work():
        nonlocal attempts
        attempts += 1
        raise ValueError("bad input")

    try:
        retry_call(work, sleep=lambda _: None)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    assert attempts == 1


def test_retry_after_is_honoured_and_capped():
    policy = RetryPolicy(max_delay=5)
    assert policy.delay(1, retry_after=3) == 3
    assert policy.delay(1, retry_after=30) == 5
