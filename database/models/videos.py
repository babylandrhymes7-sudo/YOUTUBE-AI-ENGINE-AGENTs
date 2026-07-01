"""Video model.

TODO: Keep video metadata separate from video-level analytics snapshots.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Video(UUIDPrimaryKeyMixin, TimestampMixin, Base):
	"""Persist one YouTube video and its stable metadata."""

	__tablename__ = "videos"
	__table_args__ = (
		CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="video_duration_non_negative"),
		Index("ix_videos_channel_id_published_at", "channel_id", "published_at"),
		Index("ix_videos_status", "status"),
	)

	channel_id: Mapped["UUID"] = mapped_column(
		ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
	)
	video_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
	title: Mapped[str] = mapped_column(String(255), nullable=False)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
	category: Mapped[str | None] = mapped_column(String(128), nullable=True)
	privacy_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
	language: Mapped[str | None] = mapped_column(String(16), nullable=True)
	thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
	scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
	is_short: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

	channel: Mapped["Channel"] = relationship(back_populates="videos")
	analytics_snapshots: Mapped[list["AnalyticsSnapshot"]] = relationship(back_populates="video")
	comments: Mapped[list["Comment"]] = relationship(back_populates="video", cascade="all, delete-orphan")
	tags: Mapped[list["VideoTag"]] = relationship(back_populates="video", cascade="all, delete-orphan")
	ideas: Mapped[list["Idea"]] = relationship(back_populates="video")
	predictions: Mapped[list["Prediction"]] = relationship(back_populates="video")
	recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="video")
