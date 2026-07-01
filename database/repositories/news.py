"""Repositories for news tables."""

from __future__ import annotations

from database.models import News
from database.repositories.base import BaseRepository


class NewsRepository(BaseRepository[News]):
    """Repository for news rows."""

    model = News