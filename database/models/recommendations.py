"""Recommendation model.

TODO: Keep recommendations normalized and tied to the report or idea that created them.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Recommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persist one actionable recommendation for the content workflow."""

    __tablename__ = "recommendations"
    __table_args__ = (
        Index("ix_recommendations_channel_id_created_at", "channel_id", "created_at"),
        Index("ix_recommendations_status", "status"),
        Index("ix_recommendations_priority", "priority"),
    )

    channel_id: Mapped["UUID | None"] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
    video_id: Mapped["UUID | None"] = mapped_column(ForeignKey("videos.id", ondelete="SET NULL"), nullable=True)
    report_id: Mapped["UUID | None"] = mapped_column(ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    idea_id: Mapped["UUID | None"] = mapped_column(ForeignKey("ideas.id", ondelete="SET NULL"), nullable=True)
    experiment_id: Mapped["UUID | None"] = mapped_column(ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True)
    recommendation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    action_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    channel: Mapped["Channel | None"] = relationship(back_populates="recommendations")
    video: Mapped["Video | None"] = relationship(back_populates="recommendations")
    report: Mapped["Report | None"] = relationship(back_populates="recommendations")
    idea: Mapped["Idea | None"] = relationship(back_populates="recommendations")
    experiment: Mapped["Experiment | None"] = relationship(back_populates="recommendations")
