"""News model.

TODO: Keep news articles normalized and separate from content idea generation.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class News(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persist one locally captured news article or feed item."""

    __tablename__ = "news"
    __table_args__ = (
        Index("ix_news_url", "url", unique=True),
        Index("ix_news_content_hash", "content_hash"),
        Index("ix_news_published_at", "published_at"),
        Index("ix_news_source_name", "source_name"),
        Index("ix_news_source_type", "source_type"),
        Index("ix_news_duplicate_of_id", "duplicate_of_id"),
    )

    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_html_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duplicate_of_id: Mapped["UUID | None"] = mapped_column(
        ForeignKey("news.id", ondelete="SET NULL"), nullable=True
    )
    duplicate_score: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    duplicate_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_relevant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    duplicate_of: Mapped["News | None"] = relationship(remote_side="News.id", back_populates="duplicates")
    duplicates: Mapped[list["News"]] = relationship(back_populates="duplicate_of")
