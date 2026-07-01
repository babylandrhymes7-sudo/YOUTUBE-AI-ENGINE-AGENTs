"""Tests for deterministic graph intelligence algorithms."""

from datetime import datetime, timedelta, timezone

import pytest

from graph_intelligence.analysis import (
    align_series,
    calculate_statistics,
    detect_events,
    filter_window,
    interpolate,
    pearson_correlation,
    resample,
)
from graph_intelligence.models import GraphPointInput


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def points(values: list[float], step: timedelta = timedelta(hours=1)) -> list[GraphPointInput]:
    return [GraphPointInput(START + step * index, value) for index, value in enumerate(values)]


def test_statistics_preserve_full_series_and_growth() -> None:
    result = calculate_statistics(points([10, 20, 30, 40]))

    assert result["count"] == 4
    assert result["mean"] == 25
    assert result["median"] == 25
    assert result["growth_percent"] == 300
    assert result["trend"] == "increasing"
    assert len(result["moving_average"]) == 4


def test_interpolation_marks_only_synthetic_points() -> None:
    source = [
        GraphPointInput(START, 0),
        GraphPointInput(START + timedelta(hours=3), 30),
    ]

    result = interpolate(source, timedelta(hours=1))

    assert [point.value for point in result] == [0, 10, 20, 30]
    assert [point.is_interpolated for point in result] == [False, True, True, False]


def test_resample_never_mutates_raw_points() -> None:
    source = points([1, 2, 3, 4], timedelta(hours=12))

    result = resample(source, "daily", "sum")

    assert [point.value for point in result] == [3, 7]
    assert len(source) == 4


def test_alignment_and_correlation_use_matching_timestamps() -> None:
    left = points([1, 2, 3])
    right = points([2, 4, 6])

    assert len(align_series({"left": left, "right": right})) == 3
    assert pearson_correlation(left, right) == pytest.approx(1.0)


def test_named_window_filters_from_latest_point() -> None:
    source = points(list(range(49)))

    result = filter_window(source, "last_24_hours")

    assert len(result) == 25
    assert result[0].timestamp == START + timedelta(hours=24)


def test_event_detection_finds_large_spike() -> None:
    result = detect_events(points([10, 11, 10, 11, 100, 101, 100]), z_threshold=1.5)

    assert any(event["event_type"] == "spike" for event in result)
