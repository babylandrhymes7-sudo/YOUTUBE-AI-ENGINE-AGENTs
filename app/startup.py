"""Startup hooks for the application.

TODO: Keep startup focused on validation, logging, and local directory setup.
"""

from __future__ import annotations

from pathlib import Path

from .config import settings
from .logging import configure_logging


def prepare_local_storage() -> list[Path]:
    """Create the local storage directories required by the project."""

    paths = list(settings.storage_paths.values())
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    return paths


def validate_runtime_settings() -> None:
    """Validate the minimum local runtime settings required to boot the app."""

    if not settings.database_url:
        raise ValueError("DATABASE_URL must point to the local PostgreSQL instance.")
    if not settings.ollama_base_url.startswith("http://localhost") and not settings.ollama_base_url.startswith("http://127.0.0.1"):
        raise ValueError("OLLAMA_BASE_URL must target the local Ollama server.")


def bootstrap_runtime() -> dict[str, str | int]:
    """Prepare logging, storage, and settings validation for application start."""

    configure_logging()
    prepare_local_storage()
    validate_runtime_settings()
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "app_host": settings.app_host,
        "app_port": settings.app_port,
        "storage_root": str(settings.storage_root),
        "log_dir": settings.log_dir,
    }


def create_startup_context() -> dict[str, str | int]:
    """Return the current startup context for compatibility callers."""

    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "app_host": settings.app_host,
        "app_port": settings.app_port,
    }

