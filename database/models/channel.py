"""Channel model.

TODO: Keep channel metadata normalized and separate from analytics snapshots.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Channel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
	"""Persist one YouTube channel and its stable metadata."""

	__tablename__ = "channels"
	__table_args__ = (
		CheckConstraint("length(channel_id) > 0", name="channel_id_not_empty"),
		Index("ix_channels_handle", "handle"),
		Index("ix_channels_is_active", "is_active"),
	)

	channel_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
	title: Mapped[str] = mapped_column(String(255), nullable=False)
	handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	custom_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
	country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
	thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
	published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

	videos: Mapped[list["Video"]] = relationship(back_populates="channel", cascade="all, delete-orphan")
	analytics_snapshots: Mapped[list["AnalyticsSnapshot"]] = relationship(
		back_populates="channel", cascade="all, delete-orphan"
	)
	competitors: Mapped[list["Competitor"]] = relationship(back_populates="channel")
	reports: Mapped[list["Report"]] = relationship(back_populates="channel")
	ideas: Mapped[list["Idea"]] = relationship(back_populates="channel")
	predictions: Mapped[list["Prediction"]] = relationship(back_populates="channel")
	recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="channel")
	experiments: Mapped[list["Experiment"]] = relationship(back_populates="channel")

