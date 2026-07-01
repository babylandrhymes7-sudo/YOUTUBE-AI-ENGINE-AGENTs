"""YouTube comments collector.

TODO: Keep comment ingestion limited to fetching and persisting comment threads and replies.
"""

from __future__ import annotations

from typing import Any

from app.logging import get_logger
from database.repositories.youtube import CommentRepository
from utils.dates import parse_iso_datetime

from .client import YouTubeApiClient


logger = get_logger(__name__)


class CommentCollector:
	"""Fetch and persist comments for one YouTube video."""

	def __init__(self, client: YouTubeApiClient, repository: CommentRepository) -> None:
		"""Initialize the collector with a client and repository."""

		self._client = client
		self._repository = repository

	def collect(self, video_database_id: Any, video_external_id: str) -> list[Any]:
		"""Fetch all comment threads for a video and upsert them into PostgreSQL."""

		persisted: list[Any] = []
		page_token: str | None = None
		while True:
			payload = self._client.list_comment_threads(video_external_id, page_token=page_token)
			for thread in payload.get("items", []):
				top_level_comment = thread.get("snippet", {}).get("topLevelComment", {})
				persisted.append(self._upsert_comment(video_database_id, top_level_comment, None))
				for reply in thread.get("replies", {}).get("comments", []) or []:
					persisted.append(self._upsert_comment(video_database_id, reply, top_level_comment.get("id")))
			page_token = payload.get("nextPageToken")
			if not page_token:
				break
		return persisted

	def _upsert_comment(self, video_database_id: Any, payload: dict[str, Any], parent_comment_external_id: str | None) -> Any:
		"""Insert or update one normalized comment row."""

		snippet = payload.get("snippet", {})
		comment_id = payload.get("id", "")
		data = {
			"video_id": video_database_id,
			"comment_id": comment_id,
			"parent_comment_id": None,
			"author_channel_id": snippet.get("authorChannelId", {}).get("value"),
			"author_display_name": snippet.get("authorDisplayName"),
			"author_profile_image_url": snippet.get("authorProfileImageUrl"),
			"text": snippet.get("textOriginal") or snippet.get("textDisplay") or "",
			"like_count": int(snippet.get("likeCount", 0) or 0),
			"published_at": parse_iso_datetime(snippet.get("publishedAt")),
			"updated_at_source": parse_iso_datetime(snippet.get("updatedAt")),
			"is_hearted": bool(snippet.get("moderationStatus") == "published"),
			"is_channel_owner": bool(snippet.get("authorChannelId", {}).get("value")),
		}

		if parent_comment_external_id:
			parent = self._repository.get_one_by(comment_id=parent_comment_external_id)
			if parent is not None:
				data["parent_comment_id"] = parent.id

		existing = self._repository.get_one_by(comment_id=comment_id)
		if existing is not None:
			logger.info("Updating comment {}", comment_id)
			return self._repository.update(existing, **data)

		logger.info("Creating comment {}", comment_id)
		return self._repository.create(**data)

