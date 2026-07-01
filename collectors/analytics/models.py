"""Analytics engine data contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class AnalyticsSeriesInput:
    """One numeric time series used for derived analytics calculations."""

    key: str
    values: list[float]
    timestamps: list[date] = field(default_factory=list)


@dataclass(slots=True)
class AnalyticsMetricsInput:
    """Inputs required to calculate and persist derived analytics metrics."""

    snapshot_id: Any
    channel_id: Any
    video_id: Any | None
    scope: str
    primary_series: AnalyticsSeriesInput
    ctr_series: AnalyticsSeriesInput | None = None
    retention_series: AnalyticsSeriesInput | None = None
    subscriber_series: AnalyticsSeriesInput | None = None
    upload_times: list[date] = field(default_factory=list)
    content_duration_seconds: int | None = None
    impressions: int | None = None
    clicks: int | None = None
    views: int | None = None
    subscribers_gained: int | None = None
    subscribers_at_start: int | None = None
    subscribers_at_end: int | None = None
    packaging_features: dict[str, float] = field(default_factory=dict)
    content_features: dict[str, float] = field(default_factory=dict)