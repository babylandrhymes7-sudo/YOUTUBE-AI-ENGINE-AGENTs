"""YouTube videos collector.

TODO: Keep video ingestion limited to fetching and persisting raw metadata and tags.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.logging import get_logger
from database.repositories.catalog import VideoRepository
from database.repositories.youtube import VideoTagRepository
from utils.dates import parse_iso_datetime

from .client import YouTubeApiClient


logger = get_logger(__name__)
ISO8601_DURATION_PATTERN = re.compile(
	r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


class VideoCollector:
	"""Fetch and persist channel videos, tags, and upload schedule fields."""

	def __init__(self, client: YouTubeApiClient, repository: VideoRepository, tag_repository: VideoTagRepository) -> None:
		"""Initialize the collector with a client and repositories."""

		self._client = client
		self._repository = repository
		self._tag_repository = tag_repository

	def collect(self, channel_database_id: Any, channel_external_id: str) -> list[Any]:
		"""Fetch all videos for a channel and upsert them into PostgreSQL."""

		playlist_id = self._client.get_upload_playlist_id(channel_external_id)
		if not playlist_id:
			logger.warning("No uploads playlist found for channel {}", channel_external_id)
			return []

		video_ids: list[str] = []
		page_token: str | None = None
		while True:
			payload = self._client.list_playlist_items(playlist_id, page_token=page_token)
			for item in payload.get("items", []):
				video_id = item.get("contentDetails", {}).get("videoId")
				if video_id:
					video_ids.append(video_id)
			page_token = payload.get("nextPageToken")
			if not page_token:
				break

		persisted: list[Any] = []
		for batch_start in range(0, len(video_ids), 50):
			batch = video_ids[batch_start : batch_start + 50]
			if not batch:
				continue
			payload = self._client.list_videos(batch)
			for item in payload.get("items", []):
				persisted.append(self._upsert_video(channel_database_id, item))
		return persisted

	def _upsert_video(self, channel_database_id: Any, item: dict[str, Any]) -> Any:
		"""Insert or update a single video and its normalized tag records."""

		snippet = item.get("snippet", {})
		content_details = item.get("contentDetails", {})
		status = item.get("status", {})
		live_streaming_details = item.get("liveStreamingDetails", {})
		duration_seconds = self._parse_duration(content_details.get("duration", ""))

		data = {
			"channel_id": channel_database_id,
			"video_id": item.get("id", ""),
			"title": snippet.get("title", ""),
			"description": snippet.get("description"),
			"published_at": parse_iso_datetime(snippet.get("publishedAt")),
			"duration_seconds": duration_seconds,
			"category": snippet.get("categoryId"),
			"privacy_status": status.get("privacyStatus"),
			"language": snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage"),
			"thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url")
			or snippet.get("thumbnails", {}).get("default", {}).get("url"),
			"scheduled_at": parse_iso_datetime(live_streaming_details.get("scheduledStartTime") or status.get("publishAt")),
			"status": status.get("uploadStatus") or status.get("privacyStatus") or "active",
			"is_short": bool(duration_seconds is not None and duration_seconds <= 60),
		}

		existing = self._repository.get_one_by(video_id=data["video_id"])
		if existing is not None:
			logger.info("Updating video {}", data["video_id"])
			video = self._repository.update(existing, **data)
		else:
			logger.info("Creating video {}", data["video_id"])
			video = self._repository.create(**data)

		self._tag_repository.delete_where(video_id=video.id)
		for tag in snippet.get("tags", []) or []:
			self._tag_repository.create(video_id=video.id, tag=tag)

		return video

	def _parse_duration(self, duration: str) -> int | None:
		"""Convert an ISO 8601 duration string into seconds."""

		if not duration:
			return None
		match = ISO8601_DURATION_PATTERN.match(duration)
		if not match:
			return None
		days = int(match.group("days") or 0)
		hours = int(match.group("hours") or 0)
		minutes = int(match.group("minutes") or 0)
		seconds = int(match.group("seconds") or 0)
		return days * 86400 + hours * 3600 + minutes * 60 + seconds

