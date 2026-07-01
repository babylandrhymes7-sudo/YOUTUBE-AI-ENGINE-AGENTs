"""YouTube collection engine.

TODO: Keep orchestration limited to collection and persistence, with no analysis logic.
"""

from __future__ import annotations

from datetime import date

from app.logging import get_logger
from database.repositories.catalog import (
    AnalyticsSnapshotRepository,
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
from database.repositories.youtube import CommentRepository, VideoTagRepository
from sqlalchemy.orm import Session

from .analytics import AnalyticsCollector
from .channel import ChannelCollector
from .client import YouTubeApiClient
from .comments import CommentCollector
from .videos import VideoCollector


logger = get_logger(__name__)


class YouTubeCollectionEngine:
    """Coordinate YouTube collection and persist all fetched data into PostgreSQL."""

    def __init__(self, session: Session, client: YouTubeApiClient | None = None) -> None:
        """Initialize the engine with a SQLAlchemy session and optional HTTP client."""

        self.session = session
        self.client = client or YouTubeApiClient()
        self.channel_repository = ChannelRepository(session)
        self.video_repository = VideoRepository(session)
        self.tag_repository = VideoTagRepository(session)
        self.comment_repository = CommentRepository(session)
        self.snapshot_repository = AnalyticsSnapshotRepository(session)
        self.retention_repository = RetentionGraphRepository(session)
        self.ctr_repository = CTRGraphRepository(session)
        self.view_repository = ViewGraphRepository(session)
        self.traffic_source_repository = TrafficSourceRepository(session)
        self.traffic_source_metric_repository = TrafficSourceMetricRepository(session)
        self.audience_repository = AudienceSnapshotRepository(session)
        self.country_repository = CountryRepository(session)
        self.country_metric_repository = CountryMetricRepository(session)
        self.device_repository = DeviceRepository(session)
        self.device_metric_repository = DeviceMetricRepository(session)
        self.revenue_repository = RevenueRepository(session)
        self.channel_collector = ChannelCollector(self.client, self.channel_repository)
        self.video_collector = VideoCollector(self.client, self.video_repository, self.tag_repository)
        self.comment_collector = CommentCollector(self.client, self.comment_repository)
        self.analytics_collector = AnalyticsCollector(
            self.client,
            self.snapshot_repository,
            self.retention_repository,
            self.ctr_repository,
            self.view_repository,
            self.traffic_source_repository,
            self.traffic_source_metric_repository,
            self.audience_repository,
            self.country_repository,
            self.country_metric_repository,
            self.device_repository,
            self.device_metric_repository,
            self.revenue_repository,
        )

    def collect(self, channel_id: str, start_date: date, end_date: date) -> dict[str, int]:
        """Collect channel metadata, videos, comments, and analytics into PostgreSQL."""

        logger.info("Starting YouTube collection for channel {}", channel_id)
        comment_count = 0
        videos: list[Any] = []
        with self.session.begin():
            channel = self.channel_collector.collect(channel_id)
            videos = self.video_collector.collect(channel.id, channel.channel_id)
            for video in videos:
                comment_count += len(self.comment_collector.collect(video.id, video.video_id))
            self.analytics_collector.collect_channel_analytics(channel.id, [video.id for video in videos], start_date, end_date)
        logger.info("Completed YouTube collection for channel {}", channel_id)
        return {
            "videos": len(videos),
            "comments": comment_count,
            "start_date": start_date.toordinal(),
            "end_date": end_date.toordinal(),
        }

    def close(self) -> None:
        """Close the underlying HTTP client used by the engine."""

        self.client.close()
