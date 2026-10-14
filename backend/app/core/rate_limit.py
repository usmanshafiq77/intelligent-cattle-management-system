import hashlib
import math
import threading
import time
from dataclasses import dataclass
from typing import Callable

from fastapi import HTTPException, Request, status


@dataclass
class _Window:
    count: int
    reset_at: float


class InMemoryRateLimiter:
    """Thread-safe fixed-window limiter for single-process deployments."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 10_000,
    ) -> None:
        self._clock = clock
        self._max_keys = max_keys
        self._windows: dict[str, _Window] = {}
        self._lock = threading.Lock()

    def configure(self, *, max_keys: int) -> None:
        with self._lock:
            self._max_keys = max_keys
            self._discard_expired(self._clock())
            while len(self._windows) > self._max_keys:
                self._windows.pop(next(iter(self._windows)))

    def check(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> int | None:
        """Return retry seconds when blocked, otherwise record the request."""
        now = self._clock()

        with self._lock:
            window = self._windows.get(key)

            if window is None or window.reset_at <= now:
                if len(self._windows) >= self._max_keys:
                    self._discard_expired(now)
                while len(self._windows) >= self._max_keys:
                    self._windows.pop(next(iter(self._windows)))

                self._windows[key] = _Window(
                    count=1,
                    reset_at=now + window_seconds,
                )
                return None

            if window.count >= limit:
                return max(1, math.ceil(window.reset_at - now))

            window.count += 1
            return None

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()

    def _discard_expired(self, now: float) -> None:
        expired = [
            key
            for key, window in self._windows.items()
            if window.reset_at <= now
        ]
        for key in expired:
            self._windows.pop(key, None)


auth_rate_limiter = InMemoryRateLimiter()


def enforce_rate_limit(
    request: Request,
    *,
    scope: str,
    identity: str,
    limit: int,
    window_seconds: int,
    enabled: bool,
    max_keys: int,
) -> None:
    if not enabled:
        return

    client_host = request.client.host if request.client else "unknown"
    identity_digest = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()
    auth_rate_limiter.configure(max_keys=max_keys)
    retry_values = [
        auth_rate_limiter.check(
            f"{scope}:client:{client_host}",
            limit=limit,
            window_seconds=window_seconds,
        ),
        auth_rate_limiter.check(
            f"{scope}:identity:{identity_digest}",
            limit=limit,
            window_seconds=window_seconds,
        ),
    ]
    retry_after = max(
        (value for value in retry_values if value is not None),
        default=None,
    )

    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
