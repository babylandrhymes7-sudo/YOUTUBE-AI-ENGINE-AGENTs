"""YouTube channel collector.

TODO: Keep channel ingestion limited to fetching and persisting raw channel metadata.
"""

from __future__ import annotations

from typing import Any

from app.logging import get_logger
from database.repositories.catalog import ChannelRepository
from utils.dates import parse_iso_datetime

from .client import YouTubeApiClient


logger = get_logger(__name__)


class ChannelCollector:
	"""Fetch and persist YouTube channel metadata."""

	def __init__(self, client: YouTubeApiClient, repository: ChannelRepository) -> None:
		"""Initialize the collector with a client and repository."""

		self._client = client
		self._repository = repository

	def collect(self, channel_id: str) -> Any:
		"""Fetch channel metadata and upsert it into PostgreSQL."""

		payload = self._client.get_channel(channel_id)
		items = payload.get("items", [])
		if not items:
			raise ValueError(f"No channel data returned for channel id {channel_id}")

		item = items[0]
		snippet = item.get("snippet", {})
		branding = item.get("brandingSettings", {}).get("channel", {})

		data = {
			"channel_id": item.get("id", channel_id),
			"title": snippet.get("title", ""),
			"handle": snippet.get("customUrl"),
			"description": branding.get("description") or snippet.get("description"),
			"custom_url": snippet.get("customUrl"),
			"country_code": snippet.get("country"),
			"thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url")
			or snippet.get("thumbnails", {}).get("default", {}).get("url"),
			"published_at": parse_iso_datetime(snippet.get("publishedAt")),
			"is_active": True,
		}

		existing = self._repository.get_one_by(channel_id=data["channel_id"])
		if existing is not None:
			logger.info("Updating channel {}", data["channel_id"])
			return self._repository.update(existing, **data)

		logger.info("Creating channel {}", data["channel_id"])
		return self._repository.create(**data)

