"""Logging helpers for notification delivery."""

from __future__ import annotations

from time import perf_counter

from app.logging import get_logger


class NotificationLogger:
    def __init__(self) -> None:
        self._logger = get_logger(__name__)

    def measure(self):
        started = perf_counter()

        def finish(**fields):
            elapsed_ms = (perf_counter() - started) * 1000.0
            self._logger.info("notification event {} duration_ms={:.2f}", fields, elapsed_ms)

        return finish
