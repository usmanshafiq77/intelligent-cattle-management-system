from app.core.rate_limit import InMemoryRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


def test_normal_requests_and_excessive_requests():
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock, max_keys=10)

    assert limiter.check("login:a", limit=2, window_seconds=60) is None
    assert limiter.check("login:a", limit=2, window_seconds=60) is None
    assert limiter.check("login:a", limit=2, window_seconds=60) == 60

    clock.value += 61
    assert limiter.check("login:a", limit=2, window_seconds=60) is None


def test_limiter_state_is_isolated_after_reset():
    limiter = InMemoryRateLimiter(max_keys=10)
    assert limiter.check("register:a", limit=1, window_seconds=60) is None
    assert limiter.check("register:a", limit=1, window_seconds=60)

    limiter.reset()

    assert limiter.check("register:a", limit=1, window_seconds=60) is None
