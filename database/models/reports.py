"""Report model.

TODO: Keep generated report metadata normalized and linked to one channel.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
	"""Persist a generated report and its export metadata."""

	__tablename__ = "reports"
	__table_args__ = (
		Index("ix_reports_channel_id_generated_at", "channel_id", "generated_at"),
		Index("ix_reports_report_type", "report_type"),
		Index("ix_reports_status", "status"),
	)

	channel_id: Mapped["UUID | None"] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
	report_type: Mapped[str] = mapped_column(String(64), nullable=False)
	title: Mapped[str] = mapped_column(String(255), nullable=False)
	summary: Mapped[str | None] = mapped_column(Text, nullable=True)
	generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	format: Mapped[str] = mapped_column(String(16), nullable=False, default="pdf")
	file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
	status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

	channel: Mapped["Channel | None"] = relationship(back_populates="reports")
	ideas: Mapped[list["Idea"]] = relationship(back_populates="report")
	recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="report")
	predictions: Mapped[list["Prediction"]] = relationship(back_populates="report")
