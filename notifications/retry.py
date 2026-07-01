"""Retry helpers for notification delivery."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class RetryManager:
    attempts: int = 3
    delay_seconds: float = 1.0

    def run(self, func: Callable[[], T]) -> tuple[T, int]:
        last_error: Exception | None = None
        for attempt in range(1, max(self.attempts, 1) + 1):
            try:
                return func(), attempt - 1
            except Exception as exc:  # pragma: no cover - provider/runtime safety
                last_error = exc
                if attempt < self.attempts:
                    time.sleep(self.delay_seconds)
        if last_error is not None:
            raise last_error
        raise RuntimeError("retry manager exhausted without an error")
