"""Rate limiting utilities for YouTube API access.

TODO: Keep the limiter lightweight and predictable for local collection jobs.
"""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """Throttle outbound API calls to a configured requests-per-minute budget."""

    def __init__(self, requests_per_minute: int) -> None:
        """Initialize the limiter with a fixed request budget per minute."""

        self._requests_per_minute = max(1, requests_per_minute)
        self._min_interval_seconds = 60.0 / self._requests_per_minute
        self._lock = threading.Lock()
        self._next_allowed_time = 0.0

    def acquire(self) -> None:
        """Block until the next API request is allowed."""

        with self._lock:
            now = time.monotonic()
            sleep_for = self._next_allowed_time - now
            if sleep_for > 0:
                time.sleep(sleep_for)
                now = time.monotonic()
            self._next_allowed_time = max(self._next_allowed_time, now) + self._min_interval_seconds
