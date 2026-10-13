"""Bounded, single-process traffic protection for the LOOPBACK demo gateway.

This is NOT distributed/per-device rate limiting or public-edge protection.
A real HTTPS gateway requires a shared limiter keyed by authenticated device
identity plus an independent pre-auth source quota at the reverse proxy.
"""
from collections import deque
import math
from threading import Lock
import time


class DemoSlidingWindowLimiter:
    """Bounded sliding-window request budget shared across HTTP threads."""

    def __init__(self, *, max_requests=120, window_seconds=60, clock=None):
        if (type(max_requests) is not int or not 1 <= max_requests <= 240
                or type(window_seconds) not in (int, float)
                or not math.isfinite(window_seconds)
                or not 1 <= window_seconds <= 3600
                or (clock is not None and not callable(clock))):
            raise ValueError("demo_rate_limit:invalid_configuration")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = time.monotonic if clock is None else clock
        self._events = deque()
        self._lock = Lock()
        self._previous_time = None

    def allow(self):
        """Return false BEFORE a request body or database operation begins."""
        with self._lock:
            now = self._clock()
            if type(now) not in (int, float) or not math.isfinite(now):
                return False
            # Monotonic clock rollback is not a reason to reset the budget.
            if self._previous_time is not None and now < self._previous_time:
                return False
            self._previous_time = now
            while self._events and now - self._events[0] >= self.window_seconds:
                self._events.popleft()
            if len(self._events) >= self.max_requests:
                return False
            self._events.append(now)
            return True
