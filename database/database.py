"""Database connection helpers.

TODO: Keep the local PostgreSQL URL and engine bootstrap isolated here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class Database:
    """Container for the local PostgreSQL connection settings."""

    url: str = settings.database_url
    echo: bool = False

    def is_configured(self) -> bool:
        """Return whether the local database URL has been configured."""

        return bool(self.url)

