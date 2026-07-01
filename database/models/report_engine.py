"""Append-only canonical intelligence report models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, UUIDPrimaryKeyMixin


class IntelligenceReport(UUIDPrimaryKeyMixin, Base):
    """One immutable version of a canonical structured report."""

    __tablename__ = "intelligence_reports"
    __table_args__ = (
        UniqueConstraint("logical_id", "version", name="uq_intelligence_reports_logical_version"),
        UniqueConstraint("content_hash", name="uq_intelligence_reports_content_hash"),
        CheckConstraint("version > 0", name="intelligence_report_version_positive"),
        Index("ix_intelligence_reports_generated", "generated_at"),
        Index("ix_intelligence_reports_type_generated", "report_type", "generated_at"),
        Index("ix_intelligence_reports_video_generated", "video_id", "generated_at"),
        Index("ix_intelligence_reports_game", "game"),
        Index("ix_intelligence_reports_topic", "topic"),
        Index("ix_intelligence_reports_category", "category"),
        Index("ix_intelligence_reports_week", "calendar_year", "calendar_week"),
        Index("ix_intelligence_reports_month", "calendar_year", "calendar_month"),
        Index("ix_intelligence_reports_logical_version", "logical_id", "version"),
    )

    logical_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("intelligence_reports.id", ondelete="RESTRICT"), nullable=True
    )
    report_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calendar_year: Mapped[int] = mapped_column(Integer, nullable=False)
    calendar_week: Mapped[int] = mapped_column(Integer, nullable=False)
    calendar_month: Mapped[int] = mapped_column(Integer, nullable=False)
    channel_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    video_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    game: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    canonical_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    scores_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    previous_version: Mapped["IntelligenceReport | None"] = relationship(
        remote_side="IntelligenceReport.id"
    )
    sections: Mapped[list["IntelligenceReportSection"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class IntelligenceReportSection(UUIDPrimaryKeyMixin, Base):
    """Independently loadable canonical report section."""

    __tablename__ = "intelligence_report_sections"
    __table_args__ = (
        UniqueConstraint("report_id", "section_key", name="uq_intelligence_report_section"),
        Index("ix_intelligence_report_sections_report", "report_id", "importance"),
        Index("ix_intelligence_report_sections_key", "section_key"),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_reports.id", ondelete="CASCADE"), nullable=False
    )
    section_key: Mapped[str] = mapped_column(String(128), nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[dict | list | str | int | float | None] = mapped_column(JSON, nullable=True)
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    report: Mapped["IntelligenceReport"] = relationship(back_populates="sections")
