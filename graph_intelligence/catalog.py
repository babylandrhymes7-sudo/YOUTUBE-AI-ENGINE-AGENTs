"""Supported YouTube graph types and their default aggregation semantics."""

GRAPH_TYPES: dict[str, dict[str, str]] = {
    "views": {"unit": "count", "aggregation": "sum"},
    "impressions": {"unit": "count", "aggregation": "sum"},
    "ctr": {"unit": "percent", "aggregation": "mean"},
    "watch_time": {"unit": "hours", "aggregation": "sum"},
    "average_view_duration": {"unit": "seconds", "aggregation": "mean"},
    "retention": {"unit": "ratio", "aggregation": "mean"},
    "subscribers": {"unit": "count", "aggregation": "sum"},
    "returning_viewers": {"unit": "count", "aggregation": "sum"},
    "new_viewers": {"unit": "count", "aggregation": "sum"},
    "traffic_sources": {"unit": "count", "aggregation": "sum"},
    "countries": {"unit": "count", "aggregation": "sum"},
    "devices": {"unit": "count", "aggregation": "sum"},
    "playback_locations": {"unit": "count", "aggregation": "sum"},
    "external_sources": {"unit": "count", "aggregation": "sum"},
    "youtube_search": {"unit": "count", "aggregation": "sum"},
    "suggested_videos": {"unit": "count", "aggregation": "sum"},
    "browse_features": {"unit": "count", "aggregation": "sum"},
    "notifications": {"unit": "count", "aggregation": "sum"},
    "revenue": {"unit": "currency", "aggregation": "sum"},
    "rpm": {"unit": "currency", "aggregation": "mean"},
}


def validate_graph_type(graph_type: str) -> None:
    """Reject unknown graph types so stored data remains consistently named."""

    if graph_type not in GRAPH_TYPES:
        raise ValueError(f"unsupported graph type: {graph_type}")
