"""Pure-Python analytics engine.

TODO: Keep this layer deterministic, local-only, and free of AI dependencies.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from math import sqrt
from statistics import StatisticsError, median
from typing import Any

from app.logging import get_logger
from database.repositories.catalog import AnalyticsMetricRepository
from sqlalchemy.orm import Session

from .models import AnalyticsMetricsInput, AnalyticsSeriesInput


logger = get_logger(__name__)


class AnalyticsEngine:
    """Calculate and persist derived metrics from already-collected analytics data."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AnalyticsMetricRepository(session)

    def calculate_and_store(self, payload: AnalyticsMetricsInput) -> list[Any]:
        """Calculate all configured metrics and persist them into PostgreSQL."""

        logger.info("Calculating analytics metrics for snapshot {}", payload.snapshot_id)
        metric_rows = self._build_metric_rows(payload)
        stored_rows: list[Any] = []
        with self.session.begin():
            self.repository.delete_where(snapshot_id=payload.snapshot_id)
            for metric_row in metric_rows:
                stored_rows.append(self.repository.create(**metric_row))
        logger.info("Stored {} analytics metrics for snapshot {}", len(stored_rows), payload.snapshot_id)
        return stored_rows

    def _build_metric_rows(self, payload: AnalyticsMetricsInput) -> list[dict[str, Any]]:
        rows = [
            self._metric_row(payload, "moving_average", "Moving Average", self._moving_average(payload.primary_series.values), payload.primary_series),
            self._metric_row(payload, "rolling_average", "Rolling Average", self._rolling_average(payload.primary_series.values), payload.primary_series),
            self._metric_row(payload, "median", "Median", self._safe_median(payload.primary_series.values), payload.primary_series),
            self._metric_row(payload, "growth_rate", "Growth Rate", self._growth_rate(payload.primary_series.values), payload.primary_series),
            self._metric_row(payload, "subscriber_conversion", "Subscriber Conversion", self._subscriber_conversion(payload), payload.primary_series),
            self._metric_row(payload, "ctr_trends", "CTR Trends", self._trend_value(payload.ctr_series), payload.ctr_series or payload.primary_series),
            self._metric_row(payload, "retention_trends", "Retention Trends", self._trend_value(payload.retention_series), payload.retention_series or payload.primary_series),
            self._metric_row(payload, "standard_deviation", "Standard Deviation", self._standard_deviation(payload.primary_series.values), payload.primary_series),
            self._metric_row(payload, "percentiles", "Percentiles", None, payload.primary_series, metric_text=self._percentiles_text(payload.primary_series.values)),
            self._metric_row(payload, "outliers", "Outliers", None, payload.primary_series, metric_text=self._outliers_text(payload.primary_series.values)),
            self._metric_row(payload, "upload_timing", "Upload Timing", None, payload.primary_series, metric_text=self._upload_timing_text(payload.upload_times)),
            self._metric_row(payload, "packaging_score", "Packaging Score", self._packaging_score(payload.packaging_features), payload.primary_series),
            self._metric_row(payload, "content_score", "Content Score", self._content_score(payload.content_features), payload.primary_series),
        ]
        return rows

    def _metric_row(
        self,
        payload: AnalyticsMetricsInput,
        metric_key: str,
        metric_name: str,
        metric_value: float | None,
        series: AnalyticsSeriesInput | None,
        *,
        metric_text: str | None = None,
    ) -> dict[str, Any]:
        return {
            "snapshot_id": payload.snapshot_id,
            "channel_id": payload.channel_id,
            "video_id": payload.video_id,
            "scope": payload.scope,
            "metric_key": metric_key,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "metric_text": metric_text,
            "metric_rank": None,
            "window_size": len(series.values) if series is not None else None,
            "series_points": self._series_points(series),
            "calculated_at": datetime.now(timezone.utc),
            "notes": None,
        }

    def _moving_average(self, values: list[float], window: int = 3) -> float | None:
        if not values:
            return None
        window_values = values[-window:]
        return sum(window_values) / len(window_values)

    def _rolling_average(self, values: list[float], window: int = 7) -> float | None:
        if not values:
            return None
        window_values = values[-window:]
        return sum(window_values) / len(window_values)

    def _safe_median(self, values: list[float]) -> float | None:
        if not values:
            return None
        return float(median(values))

    def _growth_rate(self, values: list[float]) -> float | None:
        if len(values) < 2 or values[0] == 0:
            return None
        return ((values[-1] - values[0]) / abs(values[0])) * 100.0

    def _subscriber_conversion(self, payload: AnalyticsMetricsInput) -> float | None:
        if payload.views in (None, 0) or payload.subscribers_gained is None:
            return None
        return (payload.subscribers_gained / payload.views) * 100.0

    def _trend_value(self, series: AnalyticsSeriesInput | None) -> float | None:
        if series is None or len(series.values) < 2:
            return None
        return series.values[-1] - series.values[0]

    def _standard_deviation(self, values: list[float]) -> float | None:
        if len(values) < 2:
            return None
        mean_value = sum(values) / len(values)
        variance = sum((value - mean_value) ** 2 for value in values) / len(values)
        return sqrt(variance)

    def _percentiles_text(self, values: list[float]) -> str | None:
        if not values:
            return None
        ordered = sorted(values)
        percentiles = {"p25": self._percentile(ordered, 0.25), "p50": self._percentile(ordered, 0.50), "p75": self._percentile(ordered, 0.75), "p90": self._percentile(ordered, 0.90)}
        return str(percentiles)

    def _outliers_text(self, values: list[float]) -> str | None:
        if len(values) < 4:
            return None
        ordered = sorted(values)
        q1 = self._percentile(ordered, 0.25)
        q3 = self._percentile(ordered, 0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outliers = [value for value in values if value < lower or value > upper]
        return str(outliers)

    def _upload_timing_text(self, upload_times: list[Any]) -> str | None:
        if not upload_times:
            return None
        hours = [value.hour for value in upload_times if hasattr(value, "hour")]
        if not hours:
            return None
        return str({"best_hour": max(set(hours), key=hours.count), "hours": hours})

    def _packaging_score(self, features: dict[str, float]) -> float | None:
        if not features:
            return None
        weights = {"title_clarity": 0.25, "thumbnail_quality": 0.25, "keyword_match": 0.20, "hook_strength": 0.20, "metadata_completeness": 0.10}
        score = sum(features.get(name, 0.0) * weight for name, weight in weights.items())
        return round(score, 4)

    def _content_score(self, features: dict[str, float]) -> float | None:
        if not features:
            return None
        weights = {"topic_fit": 0.30, "retention": 0.25, "ctr": 0.20, "engagement": 0.15, "consistency": 0.10}
        score = sum(features.get(name, 0.0) * weight for name, weight in weights.items())
        return round(score, 4)

    def _percentile(self, ordered_values: list[float], fraction: float) -> float:
        if not ordered_values:
            raise StatisticsError("percentile requires at least one value")
        index = (len(ordered_values) - 1) * fraction
        lower = int(index)
        upper = min(lower + 1, len(ordered_values) - 1)
        if lower == upper:
            return float(ordered_values[lower])
        lower_value = ordered_values[lower]
        upper_value = ordered_values[upper]
        return float(lower_value + (upper_value - lower_value) * (index - lower))

    def _series_points(self, series: AnalyticsSeriesInput | None) -> list[dict[str, Any]] | None:
        if series is None:
            return None
        points: list[dict[str, Any]] = []
        for index, value in enumerate(series.values):
            point = {"index": index, "value": value}
            if index < len(series.timestamps):
                point["date"] = series.timestamps[index].isoformat()
            points.append(point)
        return points