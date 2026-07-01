"""Video tag model for normalized tag storage.

TODO: Keep tags normalized so repeated keywords are stored once per video.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class VideoTag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persist a single tag attached to a video."""

    __tablename__ = "video_tags"
    __table_args__ = (Index("ix_video_tags_video_id_tag", "video_id", "tag", unique=True),)

    video_id: Mapped["UUID"] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    tag: Mapped[str] = mapped_column(String(255), nullable=False)

    video: Mapped["Video"] = relationship(back_populates="tags")
