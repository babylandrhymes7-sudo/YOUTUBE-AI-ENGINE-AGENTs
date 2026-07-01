"""Repositories for catalog and analytics tables.

TODO: Keep these repositories generic and free of domain-specific query logic.
"""

from __future__ import annotations

from database.models import (
    AnalyticsSnapshot,
    AudienceSnapshot,
    AnalyticsMetric,
    CTRGraph,
    Country,
    CountryMetric,
    Device,
    DeviceMetric,
    Revenue,
    RetentionGraph,
    TrafficSource,
    TrafficSourceMetric,
    ViewGraph,
    Video,
    Channel,
)
from database.repositories.base import BaseRepository


class ChannelRepository(BaseRepository[Channel]):
    """Repository for channel catalog rows."""

    model = Channel


class VideoRepository(BaseRepository[Video]):
    """Repository for video catalog rows."""

    model = Video


class AnalyticsSnapshotRepository(BaseRepository[AnalyticsSnapshot]):
    """Repository for analytics snapshot rows."""

    model = AnalyticsSnapshot


class AnalyticsMetricRepository(BaseRepository[AnalyticsMetric]):
    """Repository for derived analytics metric rows."""

    model = AnalyticsMetric


class RetentionGraphRepository(BaseRepository[RetentionGraph]):
    """Repository for retention graph rows."""

    model = RetentionGraph


class CTRGraphRepository(BaseRepository[CTRGraph]):
    """Repository for CTR graph rows."""

    model = CTRGraph


class ViewGraphRepository(BaseRepository[ViewGraph]):
    """Repository for view graph rows."""

    model = ViewGraph


class TrafficSourceRepository(BaseRepository[TrafficSource]):
    """Repository for traffic source rows."""

    model = TrafficSource


class TrafficSourceMetricRepository(BaseRepository[TrafficSourceMetric]):
    """Repository for traffic source metric rows."""

    model = TrafficSourceMetric


class AudienceSnapshotRepository(BaseRepository[AudienceSnapshot]):
    """Repository for audience snapshot rows."""

    model = AudienceSnapshot


class CountryRepository(BaseRepository[Country]):
    """Repository for country dimension rows."""

    model = Country


class CountryMetricRepository(BaseRepository[CountryMetric]):
    """Repository for country metric rows."""

    model = CountryMetric


class DeviceRepository(BaseRepository[Device]):
    """Repository for device dimension rows."""

    model = Device


class DeviceMetricRepository(BaseRepository[DeviceMetric]):
    """Repository for device metric rows."""

    model = DeviceMetric


class RevenueRepository(BaseRepository[Revenue]):
    """Repository for revenue rows."""

    model = Revenue
