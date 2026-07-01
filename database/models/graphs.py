"""Normalized, immutable graph intelligence persistence models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, UUIDPrimaryKeyMixin


class Graph(UUIDPrimaryKeyMixin, Base):
    """One graph captured during one collection run."""

    __tablename__ = "graphs"
    __table_args__ = (
        Index("ix_graphs_type_collected", "graph_type", "collected_at"),
        Index("ix_graphs_channel_type_collected", "channel_id", "graph_type", "collected_at"),
        Index("ix_graphs_video_type_collected", "video_id", "graph_type", "collected_at"),
    )

    graph_type: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_id: Mapped["UUID | None"] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=True)
    video_id: Mapped["UUID | None"] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=True)
    analytics_snapshot_id: Mapped["UUID | None"] = mapped_column(
        ForeignKey("analytics_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    timeframe: Mapped[str] = mapped_column(String(32), nullable=False, default="custom")
    resolution: Mapped[str] = mapped_column(String(32), nullable=False, default="raw")
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    point_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dominant_pattern: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    points: Mapped[list["GraphPoint"]] = relationship(
        back_populates="graph", cascade="all, delete-orphan", order_by="GraphPoint.timestamp"
    )
    statistics: Mapped["GraphStatistics | None"] = relationship(
        back_populates="graph", cascade="all, delete-orphan", uselist=False
    )
    events: Mapped[list["GraphEvent"]] = relationship(back_populates="graph", cascade="all, delete-orphan")


class GraphPoint(UUIDPrimaryKeyMixin, Base):
    """One normalized point; original observations are never overwritten."""

    __tablename__ = "graph_points"
    __table_args__ = (
        Index("ix_graph_points_graph_timestamp", "graph_id", "timestamp", unique=True),
        Index("ix_graph_points_type_timestamp", "graph_type", "timestamp"),
    )

    graph_id: Mapped["UUID"] = mapped_column(ForeignKey("graphs.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    graph_type: Mapped[str] = mapped_column(String(128), nullable=False)
    channel_id: Mapped["UUID | None"] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=True)
    video_id: Mapped["UUID | None"] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=True)
    analytics_snapshot_id: Mapped["UUID | None"] = mapped_column(
        ForeignKey("analytics_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    is_interpolated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    graph: Mapped["Graph"] = relationship(back_populates="points")


class GraphStatistics(UUIDPrimaryKeyMixin, Base):
    """Calculated statistics and summary metadata for a graph."""

    __tablename__ = "graph_statistics"
    __table_args__ = (Index("ix_graph_statistics_graph_id", "graph_id", unique=True),)

    graph_id: Mapped["UUID"] = mapped_column(ForeignKey("graphs.id", ondelete="CASCADE"), nullable=False)
    minimum: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    maximum: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    mean: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    median: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    standard_deviation: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    variance: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    growth_percent: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    slope: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    acceleration: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    volatility: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    graph: Mapped["Graph"] = relationship(back_populates="statistics")


class GraphEvent(UUIDPrimaryKeyMixin, Base):
    """An automatically detected, explainable event in a graph."""

    __tablename__ = "graph_events"
    __table_args__ = (
        Index("ix_graph_events_graph_timestamp", "graph_id", "timestamp"),
        Index("ix_graph_events_type", "event_type"),
    )

    graph_id: Mapped["UUID"] = mapped_column(ForeignKey("graphs.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    value: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    severity: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    graph: Mapped["Graph"] = relationship(back_populates="events")
