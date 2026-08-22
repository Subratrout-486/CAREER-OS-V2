from threading import Lock

from career_os.core.service_limits import ServiceLimiter


def test_same_service_is_bounded_while_different_services_are_independent():
    limiter = ServiceLimiter({"greenhouse": 1, "lever": 2})
    entered = 0
    peak = 0
    lock = Lock()

    def work():
        nonlocal entered, peak
        with lock:
            entered += 1
            peak = max(peak, entered)
        with lock:
            entered -= 1
        return "ok"

    assert limiter.run("greenhouse", work) == "ok"
    assert limiter.run("lever", work) == "ok"
    assert peak == 1


def test_default_limit_applies_to_unknown_services():
    limiter = ServiceLimiter(default_limit=2)
    assert limiter.run("unknown", lambda: 42) == 42
    assert limiter.active_service_count() == 1


def test_invalid_limit_is_rejected():
    limiter = ServiceLimiter({"greenhouse": 0})
    try:
        limiter.run("greenhouse", lambda: None)
    except ValueError:
        pass
    else:
        raise AssertionError("expected invalid service limit to fail")
