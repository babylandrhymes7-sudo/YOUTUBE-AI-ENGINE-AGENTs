"""Repository layer for the database package.

TODO: Re-export repository classes used by the application services.
"""

from database.repositories.base import BaseRepository
from database.repositories.catalog import (
    AnalyticsSnapshotRepository,
    AnalyticsMetricRepository,
    AudienceSnapshotRepository,
    CTRGraphRepository,
    CountryMetricRepository,
    CountryRepository,
    DeviceMetricRepository,
    DeviceRepository,
    RevenueRepository,
    RetentionGraphRepository,
    TrafficSourceMetricRepository,
    TrafficSourceRepository,
    ViewGraphRepository,
    VideoRepository,
    ChannelRepository,
)
from database.repositories.competitors import CompetitorRepository, CompetitorSnapshotRepository
from database.repositories.competitors import CompetitorVideoSnapshotRepository
from database.repositories.news import NewsRepository
from database.repositories.insights import (
    ExperimentRepository,
    IdeaRepository,
    MemoryRepository,
    PredictionRepository,
    RecommendationRepository,
    ReportRepository,
)
from database.repositories.youtube import CommentRepository, VideoTagRepository
