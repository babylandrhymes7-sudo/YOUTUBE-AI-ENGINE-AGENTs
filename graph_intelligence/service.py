"""High-level graph loading, normalization, analysis, comparison, and JSON export."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from .analysis import (
    align_series,
    analyze_retention_curve,
    calculate_statistics,
    detect_anomalies,
    detect_events,
    filter_window,
    pearson_correlation,
)
from .catalog import validate_graph_type
from .models import GraphInput, GraphPointInput
from .repository import GraphRepository


class GraphService:
    """Canonical non-AI interface to graph intelligence."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = GraphRepository(session)
        self._cache: dict[str, dict[str, Any]] = {}

    def ingest(self, payload: GraphInput, *, commit: bool = False) -> Any:
        """Normalize, analyze, and persist one immutable graph snapshot."""

        validate_graph_type(payload.graph_type)
        points = self._normalize_points(payload.points)
        statistics = calculate_statistics(points)
        events = detect_events(points)
        anomalies = detect_anomalies(points)
        statistics["anomalies"] = [
            {**anomaly, "timestamp": anomaly["timestamp"].isoformat()} for anomaly in anomalies
        ]
        if payload.graph_type == "retention":
            statistics["retention_analysis"] = analyze_retention_curve(points)
        graph = self.repository.create_graph(
            graph_type=payload.graph_type,
            name=payload.name,
            channel_id=payload.channel_id,
            video_id=payload.video_id,
            analytics_snapshot_id=payload.analytics_snapshot_id,
            timeframe=payload.timeframe,
            resolution=payload.resolution,
            unit=payload.unit,
            collected_at=payload.collected_at or datetime.now(timezone.utc),
            point_count=len(points),
            trend=statistics.get("trend"),
            dominant_pattern=self._dominant_pattern(payload.graph_type, statistics, events),
            metadata_json=payload.metadata or None,
        )
        self.repository.add_points(
            graph,
            [
                {
                    "timestamp": point.timestamp,
                    "value": point.value,
                    "graph_type": payload.graph_type,
                    "channel_id": payload.channel_id,
                    "video_id": payload.video_id,
                    "analytics_snapshot_id": payload.analytics_snapshot_id,
                    "is_interpolated": point.is_interpolated,
                    "metadata_json": point.metadata or None,
                }
                for point in points
            ],
        )
        self.repository.add_statistics(
            graph,
            minimum=statistics.get("minimum"),
            maximum=statistics.get("maximum"),
            mean=statistics.get("mean"),
            median=statistics.get("median"),
            standard_deviation=statistics.get("standard_deviation"),
            variance=statistics.get("variance"),
            growth_percent=statistics.get("growth_percent"),
            slope=statistics.get("slope"),
            acceleration=statistics.get("acceleration"),
            volatility=statistics.get("volatility"),
            summary_json=statistics,
            calculated_at=datetime.now(timezone.utc),
        )
        self.repository.add_events(
            graph,
            [
                {
                    "event_type": event["event_type"],
                    "timestamp": event["timestamp"],
                    "end_timestamp": event["end_timestamp"],
                    "value": event["value"],
                    "severity": event["severity"],
                    "description": event["description"],
                    "metadata_json": event["metadata"] or None,
                }
                for event in events
            ],
        )
        if commit:
            self.session.commit()
        self._cache.pop(str(graph.id), None)
        return graph

    def export_json(self, graph_id: Any, *, window: str = "lifetime", start: datetime | None = None, end: datetime | None = None) -> dict[str, Any]:
        """Return structured, JSON-safe graph intelligence suitable for Qwen."""

        cache_key = f"{graph_id}:{window}:{start}:{end}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        graph = self.repository.get_graph(graph_id)
        if graph is None:
            raise LookupError(f"graph not found: {graph_id}")
        inputs = [
            GraphPointInput(point.timestamp, float(point.value), point.metadata_json or {}, point.is_interpolated)
            for point in graph.points
        ]
        selected = filter_window(inputs, window, start, end)
        statistics = calculate_statistics(selected) if window != "lifetime" else self._json_safe(graph.statistics.summary_json or {})
        selected_timestamps = {point.timestamp for point in selected}
        result = {
            "graph_id": str(graph.id),
            "graph_name": graph.name,
            "graph_type": graph.graph_type,
            "timeframe": window if window != "lifetime" else graph.timeframe,
            "resolution": graph.resolution,
            "unit": graph.unit,
            "collected_at": graph.collected_at.isoformat(),
            "trend": statistics.get("trend", graph.trend),
            "dominant_pattern": graph.dominant_pattern,
            "statistics": statistics,
            "events": [
                {
                    "type": event.event_type,
                    "timestamp": event.timestamp.isoformat(),
                    "end_timestamp": event.end_timestamp.isoformat() if event.end_timestamp else None,
                    "value": float(event.value) if event.value is not None else None,
                    "severity": float(event.severity) if event.severity is not None else None,
                    "description": event.description,
                    "metadata": event.metadata_json or {},
                }
                for event in graph.events
                if event.timestamp in selected_timestamps
            ],
            "points": [
                {
                    "timestamp": point.timestamp.isoformat(),
                    "metric": graph.graph_type,
                    "value": point.value,
                    "metadata": point.metadata,
                    "is_interpolated": point.is_interpolated,
                }
                for point in selected
            ],
        }
        self._cache[cache_key] = result
        return result

    def compare_graphs(self, graph_ids: list[Any]) -> dict[str, Any]:
        """Align graph timestamps and return pairwise correlations."""

        series: dict[str, list[GraphPointInput]] = {}
        for graph_id in graph_ids:
            graph = self.repository.get_graph(graph_id)
            if graph is None:
                raise LookupError(f"graph not found: {graph_id}")
            series[str(graph.id)] = [GraphPointInput(point.timestamp, float(point.value)) for point in graph.points]
        correlations: dict[str, float | None] = {}
        names = list(series)
        for index, left in enumerate(names):
            for right in names[index + 1 :]:
                correlations[f"{left}:{right}"] = pearson_correlation(series[left], series[right])
        return {"aligned_points": align_series(series), "correlations": correlations}

    def _normalize_points(self, points: list[GraphPointInput]) -> list[GraphPointInput]:
        """Sort points, require timezone-aware timestamps, and reject duplicates."""

        normalized: list[GraphPointInput] = []
        seen: set[datetime] = set()
        for point in sorted(points, key=lambda item: item.timestamp):
            timestamp = point.timestamp
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            if timestamp in seen:
                raise ValueError(f"duplicate graph timestamp: {timestamp.isoformat()}")
            seen.add(timestamp)
            normalized.append(GraphPointInput(timestamp, float(point.value), point.metadata, point.is_interpolated))
        return normalized

    def _dominant_pattern(self, graph_type: str, statistics: dict[str, Any], events: list[dict[str, Any]]) -> str:
        event_types = {event["event_type"] for event in events}
        trend = statistics.get("trend", "stable")
        if graph_type == "views" and "spike" in event_types:
            return "viral_spike"
        if graph_type == "ctr" and trend == "decreasing":
            return "slow_decay" if statistics.get("volatility", 0) < 0.25 else "rapid_collapse"
        if graph_type == "retention" and "drop" in event_types:
            return "steep_decline"
        return trend

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {key: self._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        return value
