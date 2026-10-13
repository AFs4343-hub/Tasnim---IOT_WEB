"""Deterministic single-process edge budget tests; zero Firebase access."""
from concurrent.futures import ThreadPoolExecutor
import unittest

from iot.gateway_demo_rate_limit_v1 import DemoSlidingWindowLimiter


class DemoRateLimitTests(unittest.TestCase):
    def test_window_reopens_without_manual_counter_reset(self):
        current = [20.0]
        limiter = DemoSlidingWindowLimiter(
            max_requests=2, window_seconds=5, clock=lambda: current[0],
        )
        self.assertTrue(limiter.allow())
        self.assertTrue(limiter.allow())
        self.assertFalse(limiter.allow())
        current[0] = 24.999
        self.assertFalse(limiter.allow())
        current[0] = 25
        self.assertTrue(limiter.allow())

    def test_concurrent_threads_cannot_exceed_shared_budget(self):
        limiter = DemoSlidingWindowLimiter(
            max_requests=7, window_seconds=60, clock=lambda: 100,
        )
        with ThreadPoolExecutor(max_workers=20) as executor:
            outcomes = list(executor.map(lambda _: limiter.allow(), range(80)))
        self.assertEqual(sum(outcomes), 7)

    def test_clock_rollback_and_nonfinite_values_fail_closed(self):
        now = [10]
        limiter = DemoSlidingWindowLimiter(
            max_requests=3, clock=lambda: now[0],
        )
        self.assertTrue(limiter.allow())
        now[0] = 9
        self.assertFalse(limiter.allow())
        now[0] = float("nan")
        self.assertFalse(limiter.allow())
        now[0] = 11
        self.assertTrue(limiter.allow())

    def test_invalid_or_unbounded_settings_rejected(self):
        for bad in (
            {"max_requests": 0}, {"max_requests": 241},
            {"max_requests": True}, {"window_seconds": float("inf")},
            {"window_seconds": 0}, {"window_seconds": 3601},
            {"window_seconds": "60"}, {"clock": 4},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                DemoSlidingWindowLimiter(**bad)


if __name__ == "__main__":
    unittest.main()
