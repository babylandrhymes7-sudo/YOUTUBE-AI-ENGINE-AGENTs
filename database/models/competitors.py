"""Competitor models.

TODO: Keep competitor tracking normalized and separate from the channel catalog.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Competitor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
	"""Persist a competitor channel or creator that the team wants to track."""

	__tablename__ = "competitors"
	__table_args__ = (
		Index("ix_competitors_competitor_channel_id", "competitor_channel_id", unique=True),
		Index("ix_competitors_is_active", "is_active"),
	)

	channel_id: Mapped["UUID | None"] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
	competitor_channel_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
	name: Mapped[str] = mapped_column(String(255), nullable=False)
	channel_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
	niche: Mapped[str | None] = mapped_column(String(255), nullable=True)
	notes: Mapped[str | None] = mapped_column(Text, nullable=True)
	is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

	channel: Mapped["Channel | None"] = relationship(back_populates="competitors")
	snapshots: Mapped[list["CompetitorSnapshot"]] = relationship(back_populates="competitor", cascade="all, delete-orphan")


class CompetitorSnapshot(UUIDPrimaryKeyMixin, Base):
	"""Persist a competitor performance snapshot at a point in time."""

	__tablename__ = "competitor_snapshots"
	__table_args__ = (
		Index("ix_competitor_snapshots_competitor_id_collected_at", "competitor_id", "collected_at"),
		Index("ix_competitor_snapshots_channel_id_collected_at", "channel_id", "collected_at"),
	)

	competitor_id: Mapped["UUID"] = mapped_column(ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False)
	channel_id: Mapped["UUID | None"] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
	collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	subscriber_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
	view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
	video_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
	engagement_rate: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
	average_views: Mapped[int | None] = mapped_column(Integer, nullable=True)

	competitor: Mapped["Competitor"] = relationship(back_populates="snapshots")
	videos: Mapped[list["CompetitorVideoSnapshot"]] = relationship(
		back_populates="snapshot", cascade="all, delete-orphan"
	)


class CompetitorVideoSnapshot(UUIDPrimaryKeyMixin, Base):
	"""Persist a historical snapshot of one competitor video."""

	__tablename__ = "competitor_video_snapshots"
	__table_args__ = (
		Index("ix_competitor_video_snapshots_snapshot_id_collected_at", "snapshot_id", "collected_at"),
		Index("ix_competitor_video_snapshots_competitor_video_id_collected_at", "competitor_video_id", "collected_at"),
		Index("ix_competitor_video_snapshots_unique_grain", "snapshot_id", "competitor_video_id", "collected_at", unique=True),
	)

	snapshot_id: Mapped["UUID"] = mapped_column(ForeignKey("competitor_snapshots.id", ondelete="CASCADE"), nullable=False)
	competitor_video_id: Mapped[str] = mapped_column(String(64), nullable=False)
	title: Mapped[str] = mapped_column(String(512), nullable=False)
	views: Mapped[int | None] = mapped_column(Integer, nullable=True)
	upload_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
	subscriber_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
	collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

	snapshot: Mapped["CompetitorSnapshot"] = relationship(back_populates="videos")
