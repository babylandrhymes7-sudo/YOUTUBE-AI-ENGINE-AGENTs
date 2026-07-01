"""Idea model.

TODO: Keep content ideas normalized and tied back to their originating source.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Idea(UUIDPrimaryKeyMixin, TimestampMixin, Base):
	"""Persist one content idea generated from analytics or news."""

	__tablename__ = "ideas"
	__table_args__ = (
		Index("ix_ideas_channel_id_created_at", "channel_id", "created_at"),
		Index("ix_ideas_status", "status"),
	)

	channel_id: Mapped["UUID | None"] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
	report_id: Mapped["UUID | None"] = mapped_column(ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
	related_video_id: Mapped["UUID | None"] = mapped_column(ForeignKey("videos.id", ondelete="SET NULL"), nullable=True)
	title: Mapped[str] = mapped_column(String(255), nullable=False)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
	source_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
	priority: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
	status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
	due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

	channel: Mapped["Channel | None"] = relationship(back_populates="ideas")
	report: Mapped["Report | None"] = relationship(back_populates="ideas")
	video: Mapped["Video | None"] = relationship(back_populates="ideas")
	recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="idea")
