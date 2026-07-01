"""Canonical Report Engine input and search contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


REPORT_TYPES = {"daily", "weekly", "monthly", "custom", "historical", "comparison"}


@dataclass(frozen=True)
class ReportRequest:
    """Structured subsystem outputs and report metadata."""

    report_type: str
    sources: dict[str, Any]
    title: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    channel_id: str | None = None
    video_id: str | None = None
    game: str | None = None
    topic: str | None = None
    category: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    generated_at: datetime | None = None


@dataclass(frozen=True)
class ReportSearchQuery:
    """Indexed report history filters."""

    date_from: datetime | None = None
    date_to: datetime | None = None
    year: int | None = None
    week: int | None = None
    month: int | None = None
    video_id: str | None = None
    game: str | None = None
    topic: str | None = None
    category: str | None = None
    report_type: str | None = None
    latest_versions_only: bool = True
    include_archived: bool = False
    page: int = 1
    page_size: int = 50
