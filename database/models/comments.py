"""Comment model for YouTube collection.

TODO: Keep comments normalized and attached to the originating video only.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Comment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persist one YouTube comment or reply."""

    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_comment_id", "comment_id", unique=True),
        Index("ix_comments_video_id_published_at", "video_id", "published_at"),
        Index("ix_comments_parent_comment_id", "parent_comment_id"),
    )

    video_id: Mapped["UUID"] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    comment_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    parent_comment_id: Mapped["UUID | None"] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    author_channel_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    author_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_profile_image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at_source: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_hearted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_channel_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    video: Mapped["Video"] = relationship(back_populates="comments")
