"""Repositories for insight and planning tables.

TODO: Keep this layer generic so it remains easy to unit test.
"""

from __future__ import annotations

from database.models import Experiment, Idea, Memory, Prediction, Recommendation, Report
from database.repositories.base import BaseRepository


class ReportRepository(BaseRepository[Report]):
    """Repository for report rows."""

    model = Report


class IdeaRepository(BaseRepository[Idea]):
    """Repository for idea rows."""

    model = Idea


class PredictionRepository(BaseRepository[Prediction]):
    """Repository for prediction rows."""

    model = Prediction


class MemoryRepository(BaseRepository[Memory]):
    """Repository for memory rows."""

    model = Memory


class RecommendationRepository(BaseRepository[Recommendation]):
    """Repository for recommendation rows."""

    model = Recommendation


class ExperimentRepository(BaseRepository[Experiment]):
    """Repository for experiment rows."""

    model = Experiment
