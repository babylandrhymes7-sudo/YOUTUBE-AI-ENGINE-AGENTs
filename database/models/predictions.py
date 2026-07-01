"""Prediction model.

TODO: Store prediction outputs separately from source analytics and model metadata.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Prediction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
	"""Persist one machine-generated prediction for a channel or a video."""

	__tablename__ = "predictions"
	__table_args__ = (
		Index("ix_predictions_channel_id_created_at", "channel_id", "created_at"),
		Index("ix_predictions_target_type_target_id", "target_type", "target_id"),
	)

	channel_id: Mapped["UUID | None"] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
	video_id: Mapped["UUID | None"] = mapped_column(ForeignKey("videos.id", ondelete="SET NULL"), nullable=True)
	report_id: Mapped["UUID | None"] = mapped_column(ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
	target_type: Mapped[str] = mapped_column(String(64), nullable=False)
	target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
	metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
	predicted_value: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
	confidence: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
	predicted_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	forecast_horizon_days: Mapped[int | None] = mapped_column(nullable=True)
	model_name: Mapped[str] = mapped_column(String(128), nullable=False, default="qwen3.6")
	explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

	channel: Mapped["Channel | None"] = relationship(back_populates="predictions")
	video: Mapped["Video | None"] = relationship(back_populates="predictions")
	report: Mapped["Report | None"] = relationship(back_populates="predictions")
