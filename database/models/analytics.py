"""Analytics model group.

TODO: Keep analytics snapshots as the grain that all derived metrics attach to.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, UUIDPrimaryKeyMixin


class AnalyticsSnapshot(UUIDPrimaryKeyMixin, Base):
	"""Persist one analytics snapshot for a channel or a specific video."""

	__tablename__ = "analytics_snapshots"
	__table_args__ = (
		CheckConstraint("scope IN ('channel', 'video')", name="analytics_snapshot_scope_valid"),
		CheckConstraint("video_id IS NOT NULL OR scope = 'channel'", name="analytics_snapshot_video_scope_consistent"),
		Index("ix_analytics_snapshots_channel_id_collected_at", "channel_id", "collected_at"),
		Index("ix_analytics_snapshots_video_id_collected_at", "video_id", "collected_at"),
		Index("ix_analytics_snapshots_snapshot_date", "snapshot_date"),
		Index("ix_analytics_snapshots_grain", "channel_id", "video_id", "snapshot_date", "scope", unique=True),
	)

	channel_id: Mapped["UUID"] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
	video_id: Mapped["UUID | None"] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=True)
	scope: Mapped[str] = mapped_column(String(16), nullable=False, default="channel")
	snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
	collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	likes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	comments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	shares: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	click_through_rate: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
	watch_time_hours: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
	avg_view_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
	unique_viewers: Mapped[int | None] = mapped_column(Integer, nullable=True)
	subscribers_gained: Mapped[int | None] = mapped_column(Integer, nullable=True)
	notes: Mapped[str | None] = mapped_column(Text, nullable=True)

	channel: Mapped["Channel"] = relationship(back_populates="analytics_snapshots")
	video: Mapped["Video | None"] = relationship(back_populates="analytics_snapshots")
	retention_graph: Mapped[list["RetentionGraph"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")
	ctr_graph: Mapped[list["CTRGraph"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")
	view_graph: Mapped[list["ViewGraph"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")
	traffic_source_metrics: Mapped[list["TrafficSourceMetric"]] = relationship(
		back_populates="snapshot", cascade="all, delete-orphan"
	)
	audience_snapshot: Mapped["AudienceSnapshot | None"] = relationship(
		back_populates="snapshot", cascade="all, delete-orphan", uselist=False
	)
	country_metrics: Mapped[list["CountryMetric"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")
	device_metrics: Mapped[list["DeviceMetric"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")
	revenue: Mapped["Revenue | None"] = relationship(back_populates="snapshot", cascade="all, delete-orphan", uselist=False)
	derived_metrics: Mapped[list["AnalyticsMetric"]] = relationship(
		back_populates="snapshot", cascade="all, delete-orphan"
	)


class AnalyticsMetric(UUIDPrimaryKeyMixin, Base):
	"""Persist one derived analytics metric computed from raw snapshot data."""

	__tablename__ = "analytics_metrics"
	__table_args__ = (
		Index("ix_analytics_metrics_snapshot_id_metric_key", "snapshot_id", "metric_key", unique=True),
		Index("ix_analytics_metrics_metric_key", "metric_key"),
		Index("ix_analytics_metrics_scope", "scope"),
	)

	snapshot_id: Mapped["UUID"] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="CASCADE"), nullable=False)
	channel_id: Mapped["UUID"] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
	video_id: Mapped["UUID | None"] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=True)
	scope: Mapped[str] = mapped_column(String(16), nullable=False)
	metric_key: Mapped[str] = mapped_column(String(128), nullable=False)
	metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
	metric_value: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
	metric_text: Mapped[str | None] = mapped_column(Text, nullable=True)
	metric_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
	window_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
	series_points: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
	calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	notes: Mapped[str | None] = mapped_column(Text, nullable=True)

	snapshot: Mapped["AnalyticsSnapshot"] = relationship(back_populates="derived_metrics")


class RetentionGraph(UUIDPrimaryKeyMixin, Base):
	"""Persist one point in a retention graph series."""

	__tablename__ = "retention_graphs"
	__table_args__ = (
		CheckConstraint("point_index >= 0", name="retention_graph_point_index_non_negative"),
		CheckConstraint("retention_percent >= 0", name="retention_graph_retention_non_negative"),
		Index("ix_retention_graphs_snapshot_id_point_index", "snapshot_id", "point_index", unique=True),
	)

	snapshot_id: Mapped["UUID"] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="CASCADE"), nullable=False)
	point_index: Mapped[int] = mapped_column(Integer, nullable=False)
	elapsed_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
	retention_percent: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

	snapshot: Mapped["AnalyticsSnapshot"] = relationship(back_populates="retention_graph")


class CTRGraph(UUIDPrimaryKeyMixin, Base):
	"""Persist one point in a click-through-rate graph series."""

	__tablename__ = "ctr_graphs"
	__table_args__ = (
		CheckConstraint("point_index >= 0", name="ctr_graph_point_index_non_negative"),
		CheckConstraint("ctr_percent >= 0", name="ctr_graph_ctr_non_negative"),
		Index("ix_ctr_graphs_snapshot_id_point_index", "snapshot_id", "point_index", unique=True),
	)

	snapshot_id: Mapped["UUID"] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="CASCADE"), nullable=False)
	point_index: Mapped[int] = mapped_column(Integer, nullable=False)
	elapsed_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
	impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	ctr_percent: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

	snapshot: Mapped["AnalyticsSnapshot"] = relationship(back_populates="ctr_graph")


class ViewGraph(UUIDPrimaryKeyMixin, Base):
	"""Persist one point in a views graph series."""

	__tablename__ = "view_graphs"
	__table_args__ = (
		CheckConstraint("point_index >= 0", name="view_graph_point_index_non_negative"),
		CheckConstraint("views >= 0", name="view_graph_views_non_negative"),
		Index("ix_view_graphs_snapshot_id_point_index", "snapshot_id", "point_index", unique=True),
	)

	snapshot_id: Mapped["UUID"] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="CASCADE"), nullable=False)
	point_index: Mapped[int] = mapped_column(Integer, nullable=False)
	observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	views: Mapped[int] = mapped_column(Integer, nullable=False)

	snapshot: Mapped["AnalyticsSnapshot"] = relationship(back_populates="view_graph")


class TrafficSource(UUIDPrimaryKeyMixin, Base):
	"""Normalize traffic source dimensions such as browse, search, or suggested."""

	__tablename__ = "traffic_sources"
	__table_args__ = (
		Index("ix_traffic_sources_source_key", "source_key", unique=True),
		Index("ix_traffic_sources_source_type", "source_type"),
	)

	source_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
	source_type: Mapped[str] = mapped_column(String(64), nullable=False)
	name: Mapped[str] = mapped_column(String(255), nullable=False)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)

	metrics: Mapped[list["TrafficSourceMetric"]] = relationship(back_populates="traffic_source")


class TrafficSourceMetric(UUIDPrimaryKeyMixin, Base):
	"""Persist one traffic-source metric row for a snapshot."""

	__tablename__ = "traffic_source_metrics"
	__table_args__ = (
		CheckConstraint("views >= 0", name="traffic_source_metrics_views_non_negative"),
		CheckConstraint("impressions >= 0", name="traffic_source_metrics_impressions_non_negative"),
		Index("ix_traffic_source_metrics_snapshot_source", "snapshot_id", "traffic_source_id", unique=True),
	)

	snapshot_id: Mapped["UUID"] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="CASCADE"), nullable=False)
	traffic_source_id: Mapped["UUID"] = mapped_column(ForeignKey("traffic_sources.id", ondelete="CASCADE"), nullable=False)
	views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	watch_time_hours: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
	impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	ctr_percent: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)

	snapshot: Mapped["AnalyticsSnapshot"] = relationship(back_populates="traffic_source_metrics")
	traffic_source: Mapped["TrafficSource"] = relationship(back_populates="metrics")


class AudienceSnapshot(UUIDPrimaryKeyMixin, Base):
	"""Persist audience aggregates for a given analytics snapshot."""

	__tablename__ = "audience_snapshots"
	__table_args__ = (Index("ix_audience_snapshots_snapshot_id", "snapshot_id", unique=True),)

	snapshot_id: Mapped["UUID"] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="CASCADE"), nullable=False)
	total_viewers: Mapped[int | None] = mapped_column(Integer, nullable=True)
	new_viewers: Mapped[int | None] = mapped_column(Integer, nullable=True)
	returning_viewers: Mapped[int | None] = mapped_column(Integer, nullable=True)
	subscribers: Mapped[int | None] = mapped_column(Integer, nullable=True)
	non_subscribers: Mapped[int | None] = mapped_column(Integer, nullable=True)
	avg_view_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
	average_percent_viewed: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)

	snapshot: Mapped["AnalyticsSnapshot"] = relationship(back_populates="audience_snapshot")


class Country(UUIDPrimaryKeyMixin, Base):
	"""Normalize countries for audience analytics."""

	__tablename__ = "countries"
	__table_args__ = (
		CheckConstraint("length(country_code) = 2", name="country_code_length"),
		Index("ix_countries_country_code", "country_code", unique=True),
	)

	country_code: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
	name: Mapped[str] = mapped_column(String(128), nullable=False)
	region: Mapped[str | None] = mapped_column(String(128), nullable=True)

	metrics: Mapped[list["CountryMetric"]] = relationship(back_populates="country")


class CountryMetric(UUIDPrimaryKeyMixin, Base):
	"""Persist country-level performance for one analytics snapshot."""

	__tablename__ = "country_metrics"
	__table_args__ = (
		CheckConstraint("views >= 0", name="country_metrics_views_non_negative"),
		Index("ix_country_metrics_snapshot_country", "snapshot_id", "country_id", unique=True),
	)

	snapshot_id: Mapped["UUID"] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="CASCADE"), nullable=False)
	country_id: Mapped["UUID"] = mapped_column(ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)
	views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	watch_time_hours: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
	impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	engagement_rate: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)

	snapshot: Mapped["AnalyticsSnapshot"] = relationship(back_populates="country_metrics")
	country: Mapped["Country"] = relationship(back_populates="metrics")


class Device(UUIDPrimaryKeyMixin, Base):
	"""Normalize device categories for audience analytics."""

	__tablename__ = "devices"
	__table_args__ = (Index("ix_devices_name", "name", unique=True),)

	name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)

	metrics: Mapped[list["DeviceMetric"]] = relationship(back_populates="device")


class DeviceMetric(UUIDPrimaryKeyMixin, Base):
	"""Persist device-level performance for one analytics snapshot."""

	__tablename__ = "device_metrics"
	__table_args__ = (
		CheckConstraint("views >= 0", name="device_metrics_views_non_negative"),
		Index("ix_device_metrics_snapshot_device", "snapshot_id", "device_id", unique=True),
	)

	snapshot_id: Mapped["UUID"] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="CASCADE"), nullable=False)
	device_id: Mapped["UUID"] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
	views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
	watch_time_hours: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
	share_of_watch_time: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)

	snapshot: Mapped["AnalyticsSnapshot"] = relationship(back_populates="device_metrics")
	device: Mapped["Device"] = relationship(back_populates="metrics")


class Revenue(UUIDPrimaryKeyMixin, Base):
	"""Persist revenue metrics for one analytics snapshot."""

	__tablename__ = "revenues"
	__table_args__ = (Index("ix_revenues_snapshot_id", "snapshot_id", unique=True),)

	snapshot_id: Mapped["UUID"] = mapped_column(ForeignKey("analytics_snapshots.id", ondelete="CASCADE"), nullable=False)
	currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
	estimated_revenue: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
	ad_revenue: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
	rpm: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
	cpm: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
	memberships_revenue: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
	super_chat_revenue: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
	merch_revenue: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)

	snapshot: Mapped["AnalyticsSnapshot"] = relationship(back_populates="revenue")
