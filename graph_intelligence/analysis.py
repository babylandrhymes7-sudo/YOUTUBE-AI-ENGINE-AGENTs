"""Pure-Python graph statistics, event detection, and time-series utilities."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from math import sqrt
from statistics import mean, median, pvariance
from typing import Any, Iterable

from .models import GraphPointInput


def percentile(values: list[float], fraction: float) -> float | None:
    """Return a linearly interpolated percentile."""

    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def moving_average(values: list[float], window: int = 3) -> list[float | None]:
    """Calculate a trailing moving average without discarding positions."""

    if window < 1:
        raise ValueError("window must be at least 1")
    return [None if index + 1 < window else mean(values[index + 1 - window : index + 1]) for index in range(len(values))]


def exponential_moving_average(values: list[float], span: int = 3) -> list[float]:
    """Calculate an exponential moving average."""

    if span < 1:
        raise ValueError("span must be at least 1")
    if not values:
        return []
    alpha = 2.0 / (span + 1.0)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1.0 - alpha) * result[-1])
    return result


def calculate_statistics(points: list[GraphPointInput]) -> dict[str, Any]:
    """Calculate stable summary and derived statistics for normalized points."""

    ordered = sorted(points, key=lambda point: point.timestamp)
    values = [point.value for point in ordered]
    if not values:
        return {"count": 0, "percentiles": {}, "moving_average": [], "exponential_moving_average": []}
    variance = pvariance(values) if len(values) > 1 else 0.0
    standard_deviation = sqrt(variance)
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    rates = [
        (values[index] - values[index - 1]) / abs(values[index - 1]) * 100.0
        if values[index - 1] != 0
        else None
        for index in range(1, len(values))
    ]
    x_mean = (len(values) - 1) / 2.0
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    slope = sum((index - x_mean) * (value - mean(values)) for index, value in enumerate(values)) / denominator if denominator else 0.0
    acceleration = mean([changes[index] - changes[index - 1] for index in range(1, len(changes))]) if len(changes) > 1 else 0.0
    growth = ((values[-1] - values[0]) / abs(values[0]) * 100.0) if values[0] != 0 else None
    trend = classify_trend(values, slope, standard_deviation)
    return {
        "count": len(values),
        "minimum": min(values),
        "maximum": max(values),
        "mean": mean(values),
        "median": median(values),
        "standard_deviation": standard_deviation,
        "variance": variance,
        "percentiles": {f"p{value}": percentile(values, value / 100) for value in (10, 25, 50, 75, 90, 95, 99)},
        "moving_average": moving_average(values, min(3, len(values))),
        "exponential_moving_average": exponential_moving_average(values, min(3, len(values))),
        "rate_of_change": changes,
        "percent_change": rates,
        "growth_percent": growth,
        "slope": slope,
        "acceleration": acceleration,
        "volatility": standard_deviation / abs(mean(values)) if mean(values) else 0.0,
        "trend": trend,
        "peak": {"timestamp": ordered[values.index(max(values))].timestamp.isoformat(), "value": max(values)},
        "lowest_point": {"timestamp": ordered[values.index(min(values))].timestamp.isoformat(), "value": min(values)},
    }


def classify_trend(values: list[float], slope: float, stddev: float) -> str:
    """Classify a series using scale-aware slope and volatility."""

    if len(values) < 2:
        return "stable"
    scale = abs(mean(values)) or max(abs(value) for value in values) or 1.0
    if stddev / scale > 0.5:
        return "highly_volatile"
    normalized_slope = slope / scale
    if abs(normalized_slope) < 0.005:
        return "flat"
    midpoint = max(1, len(values) // 2)
    first = values[midpoint - 1] - values[0]
    second = values[-1] - values[midpoint]
    if first < 0 < second:
        return "recovering"
    if first > 0 > second:
        return "declining"
    return "increasing" if slope > 0 else "decreasing"


def detect_events(points: list[GraphPointInput], z_threshold: float = 2.5, flat_tolerance: float = 0.005) -> list[dict[str, Any]]:
    """Detect explainable spikes, drops, flats, reversals, and recoveries."""

    ordered = sorted(points, key=lambda point: point.timestamp)
    values = [point.value for point in ordered]
    if len(values) < 2:
        return []
    differences = [values[index] - values[index - 1] for index in range(1, len(values))]
    diff_mean = mean(differences)
    diff_std = sqrt(pvariance(differences)) if len(differences) > 1 else 0.0
    events: list[dict[str, Any]] = []
    flat_start: int | None = None
    for index in range(1, len(values)):
        change = differences[index - 1]
        z_score = (change - diff_mean) / diff_std if diff_std else 0.0
        if abs(z_score) >= z_threshold:
            events.append(_event("spike" if change > 0 else "drop", ordered[index], abs(z_score), {"change": change, "z_score": z_score}))
        scale = abs(values[index - 1]) or 1.0
        is_flat = abs(change) / scale <= flat_tolerance
        if is_flat and flat_start is None:
            flat_start = index - 1
        if not is_flat and flat_start is not None:
            if index - flat_start >= 3:
                events.append(_event("long_flat_region", ordered[flat_start], index - flat_start, {}, ordered[index - 1].timestamp))
            flat_start = None
        if index >= 2:
            previous = differences[index - 2]
            if previous * change < 0:
                event_type = "sudden_recovery" if previous < 0 < change else "trend_reversal"
                events.append(_event(event_type, ordered[index], abs(change - previous), {"previous_change": previous, "change": change}))
            acceleration = change - previous
            threshold = diff_std or max(abs(diff_mean), 1.0)
            if abs(acceleration) > threshold:
                events.append(_event("acceleration" if acceleration > 0 else "deceleration", ordered[index], abs(acceleration), {"acceleration": acceleration}))
    if flat_start is not None and len(values) - flat_start >= 3:
        events.append(_event("long_flat_region", ordered[flat_start], len(values) - flat_start, {}, ordered[-1].timestamp))
    return events


def detect_anomalies(points: list[GraphPointInput], z_threshold: float = 3.0, rolling_window: int = 5) -> list[dict[str, Any]]:
    """Combine Z-score, rolling deviation, IQR, percent-change, and change-point signals."""

    ordered = sorted(points, key=lambda point: point.timestamp)
    values = [point.value for point in ordered]
    if len(values) < 2:
        return []
    overall_mean = mean(values)
    overall_std = sqrt(pvariance(values)) if len(values) > 1 else 0.0
    q1, q3 = percentile(values, 0.25), percentile(values, 0.75)
    iqr = (q3 or 0.0) - (q1 or 0.0)
    anomalies: list[dict[str, Any]] = []
    for index, point in enumerate(ordered):
        methods: list[str] = []
        scores: dict[str, float] = {}
        z_score = (point.value - overall_mean) / overall_std if overall_std else 0.0
        if abs(z_score) >= z_threshold:
            methods.append("z_score")
            scores["z_score"] = z_score
        if iqr and (point.value < (q1 or 0.0) - 1.5 * iqr or point.value > (q3 or 0.0) + 1.5 * iqr):
            methods.append("iqr_outlier")
        if index:
            previous = values[index - 1]
            percent_change = (point.value - previous) / abs(previous) * 100.0 if previous else 0.0
            scores["percent_change"] = percent_change
            if abs(percent_change) >= 100.0:
                methods.append("percent_change")
        if index >= rolling_window:
            window = values[index - rolling_window : index]
            rolling_mean = mean(window)
            rolling_std = sqrt(pvariance(window)) if len(window) > 1 else 0.0
            rolling_z = (point.value - rolling_mean) / rolling_std if rolling_std else 0.0
            scores["rolling_z_score"] = rolling_z
            if abs(rolling_z) >= z_threshold:
                methods.extend(["rolling_mean", "rolling_std"])
        if index >= 2:
            before = values[index - 1] - values[index - 2]
            after = values[index] - values[index - 1]
            if before * after < 0 and abs(after - before) > overall_std:
                methods.append("change_point")
        if methods:
            anomalies.append(
                {
                    "timestamp": point.timestamp,
                    "value": point.value,
                    "methods": sorted(set(methods)),
                    "scores": scores,
                }
            )
    return anomalies


def analyze_retention_curve(points: list[GraphPointInput]) -> dict[str, Any]:
    """Extract retention-specific drops, recovery sections, flats, and peak interest."""

    ordered = sorted(points, key=lambda point: point.timestamp)
    if not ordered:
        return {}
    differences = [ordered[index].value - ordered[index - 1].value for index in range(1, len(ordered))]
    drops = [(index + 1, change) for index, change in enumerate(differences) if change < 0]
    recoveries = [(index + 1, change) for index, change in enumerate(differences) if change > 0]
    flat_sections = [
        {"start_index": index - 1, "end_index": index}
        for index, change in enumerate(differences, start=1)
        if abs(change) <= 0.005
    ]
    largest_drop = min(drops, key=lambda item: item[1]) if drops else None
    peak_index = max(range(len(ordered)), key=lambda index: ordered[index].value)
    return {
        "largest_drop": (
            {"point_index": largest_drop[0], "value": largest_drop[1], "timestamp": ordered[largest_drop[0]].timestamp.isoformat()}
            if largest_drop
            else None
        ),
        "steepest_decline": largest_drop[1] if largest_drop else 0.0,
        "average_decline": mean(change for _, change in drops) if drops else 0.0,
        "recovery_sections": [{"point_index": index, "gain": change} for index, change in recoveries],
        "flat_sections": flat_sections,
        "peak_interest": {
            "point_index": peak_index,
            "value": ordered[peak_index].value,
            "timestamp": ordered[peak_index].timestamp.isoformat(),
        },
    }


def _event(event_type: str, point: GraphPointInput, severity: float, metadata: dict[str, Any], end: datetime | None = None) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "timestamp": point.timestamp,
        "end_timestamp": end,
        "value": point.value,
        "severity": severity,
        "description": event_type.replace("_", " ").title(),
        "metadata": metadata,
    }


def filter_window(points: Iterable[GraphPointInput], window: str, start: datetime | None = None, end: datetime | None = None) -> list[GraphPointInput]:
    """Filter points to a named or custom analysis window."""

    ordered = sorted(points, key=lambda point: point.timestamp)
    if not ordered or window == "lifetime":
        return ordered
    end = end or ordered[-1].timestamp
    durations = {"last_hour": timedelta(hours=1), "last_24_hours": timedelta(hours=24), "last_7_days": timedelta(days=7), "last_28_days": timedelta(days=28), "last_90_days": timedelta(days=90)}
    if window == "custom":
        if start is None:
            raise ValueError("custom window requires start")
    elif window in durations:
        start = end - durations[window]
    else:
        raise ValueError(f"unsupported window: {window}")
    return [point for point in ordered if start <= point.timestamp <= end]


def resample(points: Iterable[GraphPointInput], frequency: str, aggregation: str = "sum") -> list[GraphPointInput]:
    """Aggregate raw points into hourly, daily, weekly, or monthly buckets."""

    buckets: dict[datetime, list[GraphPointInput]] = defaultdict(list)
    for point in points:
        timestamp = point.timestamp
        if frequency == "hourly":
            bucket = timestamp.replace(minute=0, second=0, microsecond=0)
        elif frequency == "daily":
            bucket = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        elif frequency == "weekly":
            day = timestamp - timedelta(days=timestamp.weekday())
            bucket = day.replace(hour=0, minute=0, second=0, microsecond=0)
        elif frequency == "monthly":
            bucket = timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"unsupported frequency: {frequency}")
        buckets[bucket].append(point)
    reducers = {"sum": sum, "mean": mean, "min": min, "max": max}
    if aggregation not in reducers:
        raise ValueError(f"unsupported aggregation: {aggregation}")
    return [
        GraphPointInput(timestamp=bucket, value=float(reducers[aggregation]([point.value for point in grouped])), metadata={"source_points": len(grouped), "aggregation": aggregation})
        for bucket, grouped in sorted(buckets.items())
    ]


def interpolate(points: Iterable[GraphPointInput], interval: timedelta) -> list[GraphPointInput]:
    """Linearly fill missing fixed-interval points and mark every synthetic value."""

    if interval.total_seconds() <= 0:
        raise ValueError("interval must be positive")
    ordered = sorted(points, key=lambda point: point.timestamp)
    result: list[GraphPointInput] = []
    for left, right in zip(ordered, ordered[1:]):
        result.append(left)
        gap_count = int((right.timestamp - left.timestamp) / interval)
        for step in range(1, gap_count):
            ratio = step / gap_count
            result.append(GraphPointInput(left.timestamp + interval * step, left.value + (right.value - left.value) * ratio, {"method": "linear"}, True))
    if ordered:
        result.append(ordered[-1])
    return result


def align_series(series: dict[str, Iterable[GraphPointInput]]) -> list[dict[str, Any]]:
    """Inner-align multiple graphs by exact timestamp for correlation/comparison."""

    mapped = {name: {point.timestamp: point.value for point in points} for name, points in series.items()}
    if not mapped:
        return []
    timestamps = set.intersection(*(set(values) for values in mapped.values()))
    return [{"timestamp": timestamp, **{name: values[timestamp] for name, values in mapped.items()}} for timestamp in sorted(timestamps)]


def pearson_correlation(left: Iterable[GraphPointInput], right: Iterable[GraphPointInput]) -> float | None:
    """Return Pearson correlation after timestamp alignment."""

    rows = align_series({"left": left, "right": right})
    if len(rows) < 2:
        return None
    left_values = [row["left"] for row in rows]
    right_values = [row["right"] for row in rows]
    left_mean, right_mean = mean(left_values), mean(right_values)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left_values, right_values))
    denominator = sqrt(sum((x - left_mean) ** 2 for x in left_values) * sum((y - right_mean) ** 2 for y in right_values))
    return numerator / denominator if denominator else None
