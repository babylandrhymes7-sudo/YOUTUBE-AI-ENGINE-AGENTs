"""Logging configuration for local development and production.

TODO: Extend sinks and formatters when module-specific observability is required.
"""

from __future__ import annotations

import logging as stdlib_logging
import sys
from pathlib import Path

from loguru import logger

from .config import settings


class InterceptHandler(stdlib_logging.Handler):
    """Route standard-library logging records into Loguru."""

    def emit(self, record: stdlib_logging.LogRecord) -> None:
        """Forward a standard-library log record to Loguru."""

        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = stdlib_logging.currentframe(), 2
        while frame and frame.f_code.co_filename == stdlib_logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging() -> None:
    """Configure application logging sinks for console and local files."""

    log_directory = Path(settings.log_dir)
    log_directory.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(sys.stdout, level=settings.log_level, enqueue=True, backtrace=False, diagnose=False)
    logger.add(
        log_directory / "app.log",
        level=settings.log_level,
        rotation="10 MB",
        retention="14 days",
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )

    stdlib_logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


def get_logger(name: str) -> stdlib_logging.Logger:
    """Return a standard-library logger wired through Loguru."""

    return stdlib_logging.getLogger(name)
