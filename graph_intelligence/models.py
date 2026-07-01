"""Transport-neutral input and output contracts for graph intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class GraphPointInput:
    """One raw or interpolated observation in a metric series."""

    timestamp: datetime
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)
    is_interpolated: bool = False


@dataclass(frozen=True)
class GraphInput:
    """A complete graph captured during one immutable collection run."""

    graph_type: str
    name: str
    points: list[GraphPointInput]
    channel_id: Any | None = None
    video_id: Any | None = None
    analytics_snapshot_id: Any | None = None
    timeframe: str = "custom"
    resolution: str = "raw"
    unit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    collected_at: datetime | None = None
