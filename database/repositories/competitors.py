"""Repositories for competitor tables.

TODO: Keep this layer generic so it only coordinates persistence operations.
"""

from __future__ import annotations

from database.models import Competitor, CompetitorSnapshot, CompetitorVideoSnapshot
from database.repositories.base import BaseRepository


class CompetitorRepository(BaseRepository[Competitor]):
    """Repository for competitor catalog rows."""

    model = Competitor


class CompetitorSnapshotRepository(BaseRepository[CompetitorSnapshot]):
    """Repository for competitor snapshot rows."""

    model = CompetitorSnapshot


class CompetitorVideoSnapshotRepository(BaseRepository[CompetitorVideoSnapshot]):
    """Repository for competitor video snapshot rows."""

    model = CompetitorVideoSnapshot


