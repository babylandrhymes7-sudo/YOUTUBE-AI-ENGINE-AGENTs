"""Experiment model.

TODO: Keep content and analytics experiments normalized and auditable.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Experiment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persist one structured experiment such as an A/B content test."""

    __tablename__ = "experiments"
    __table_args__ = (
        Index("ix_experiments_channel_id_start_at", "channel_id", "start_at"),
        Index("ix_experiments_name", "name", unique=True),
        Index("ix_experiments_status", "status"),
    )

    channel_id: Mapped["UUID | None"] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    target_metric: Mapped[str] = mapped_column(String(128), nullable=False)
    control_variant: Mapped[str | None] = mapped_column(String(128), nullable=True)
    treatment_variant: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    results: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    channel: Mapped["Channel | None"] = relationship(back_populates="experiments")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="experiment")
