"""Repositories for YouTube-specific content tables.

TODO: Keep these repositories thin and reusable for the collection engine.
"""

from __future__ import annotations

from database.models import Comment, VideoTag
from database.repositories.base import BaseRepository


class CommentRepository(BaseRepository[Comment]):
    """Repository for YouTube comments."""

    model = Comment


class VideoTagRepository(BaseRepository[VideoTag]):
    """Repository for YouTube video tags."""

    model = VideoTag
