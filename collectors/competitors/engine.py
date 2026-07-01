"""Competitor collection engine.

TODO: Keep this engine limited to ingesting public YouTube competitor data and storing snapshots.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.logging import get_logger
from collectors.youtube.client import YouTubeApiClient
from database.repositories.competitors import (
    CompetitorRepository,
    CompetitorSnapshotRepository,
    CompetitorVideoSnapshotRepository,
)
from sqlalchemy.orm import Session
from utils.dates import parse_iso_datetime


logger = get_logger(__name__)


class CompetitorEngine:
    """Monitor configured YouTube competitor channels and persist historical snapshots."""

    def __init__(self, session: Session, client: YouTubeApiClient | None = None) -> None:
        """Initialize the engine with a database session and an optional shared YouTube client."""

        self.session = session
        self.client = client or YouTubeApiClient()
        self.competitor_repository = CompetitorRepository(session)
        self.snapshot_repository = CompetitorSnapshotRepository(session)
        self.video_snapshot_repository = CompetitorVideoSnapshotRepository(session)

    def collect(self, channel_ids: list[str] | None = None) -> dict[str, int]:
        """Collect competitor snapshots for configured or provided YouTube channel ids."""

        resolved_channel_ids = channel_ids or self._configured_channel_ids()
        collected_channels = 0
        collected_videos = 0

        with self.session.begin():
            for channel_id in resolved_channel_ids:
                competitor = self._upsert_competitor(channel_id)
                snapshot = self._upsert_competitor_snapshot(competitor)
                video_count = self._collect_competitor_videos(competitor, snapshot)
                collected_channels += 1
                collected_videos += video_count

        logger.info("Collected competitor data for {} channels", collected_channels)
        return {"channels": collected_channels, "videos": collected_videos}

    def close(self) -> None:
        """Close the shared YouTube client."""

        self.client.close()

    def _configured_channel_ids(self) -> list[str]:
        """Resolve competitor channels from environment configuration and database rows."""

        configured_ids = [value.strip() for value in settings.competitor_channel_ids.split(",") if value.strip()]
        db_ids = [competitor.competitor_channel_id for competitor in self.competitor_repository.list(limit=10_000)]
        merged: list[str] = []
        for channel_id in configured_ids + db_ids:
            if channel_id not in merged:
                merged.append(channel_id)
        return merged

    def _upsert_competitor(self, channel_id: str) -> Any:
        """Persist the competitor channel itself and return the ORM object."""

        payload = self.client.get_channel(channel_id)
        items = payload.get("items", [])
        if not items:
            raise ValueError(f"No channel data returned for competitor channel id {channel_id}")

        item = items[0]
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})

        data = {
            "competitor_channel_id": item.get("id", channel_id),
            "name": snippet.get("title", channel_id),
            "channel_url": f"https://www.youtube.com/channel/{item.get('id', channel_id)}",
            "niche": None,
            "notes": None,
            "is_active": True,
        }

        existing = self.competitor_repository.get_one_by(competitor_channel_id=data["competitor_channel_id"])
        if existing is not None:
            logger.info("Updating competitor channel {}", data["competitor_channel_id"])
            competitor = self.competitor_repository.update(existing, **data)
        else:
            logger.info("Creating competitor channel {}", data["competitor_channel_id"])
            competitor = self.competitor_repository.create(**data)

        subscriber_count = self._safe_int(statistics.get("subscriberCount"))
        view_count = self._safe_int(statistics.get("viewCount"))
        video_count = self._safe_int(statistics.get("videoCount"))

        return competitor, subscriber_count, view_count, video_count

    def _upsert_competitor_snapshot(self, competitor_result: tuple[Any, int | None, int | None, int | None]) -> Any:
        """Persist one historical snapshot for a competitor channel."""

        competitor, subscriber_count, view_count, video_count = competitor_result
        collected_at = datetime.now(timezone.utc)
        existing = self.snapshot_repository.get_one_by(competitor_id=competitor.id, collected_at=collected_at)
        data = {
            "competitor_id": competitor.id,
            "channel_id": competitor.channel_id,
            "collected_at": collected_at,
            "subscriber_count": subscriber_count,
            "view_count": view_count,
            "video_count": video_count,
            "engagement_rate": None,
            "average_views": None,
        }
        if existing is not None:
            return self.snapshot_repository.update(existing, **data)
        return self.snapshot_repository.create(**data)

    def _collect_competitor_videos(self, competitor_result: tuple[Any, int | None, int | None, int | None], snapshot: Any) -> int:
        """Fetch competitor videos and persist one historical row per video."""

        competitor, _, _, _ = competitor_result
        uploads_playlist_id = self.client.get_upload_playlist_id(competitor.competitor_channel_id)
        if not uploads_playlist_id:
            logger.warning("No uploads playlist found for competitor {}", competitor.competitor_channel_id)
            return 0

        video_ids: list[str] = []
        page_token: str | None = None
        while True:
            payload = self.client.list_playlist_items(uploads_playlist_id, page_token=page_token)
            for item in payload.get("items", []) or []:
                video_id = item.get("contentDetails", {}).get("videoId")
                if video_id:
                    video_ids.append(video_id)
            page_token = payload.get("nextPageToken")
            if not page_token:
                break

        persisted_count = 0
        for batch_start in range(0, len(video_ids), 50):
            batch = video_ids[batch_start : batch_start + 50]
            if not batch:
                continue
            payload = self.client.list_videos(batch)
            for item in payload.get("items", []) or []:
                self._upsert_competitor_video_snapshot(snapshot.id, item, competitor_result[1])
                persisted_count += 1
        return persisted_count

    def _upsert_competitor_video_snapshot(self, snapshot_id: Any, item: dict[str, Any], subscriber_count: int | None) -> Any:
        """Persist one competitor video snapshot row."""

        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})
        statistics = item.get("statistics", {})
        duration_seconds = self._parse_duration(content_details.get("duration", ""))

        data = {
            "snapshot_id": snapshot_id,
            "competitor_video_id": item.get("id", ""),
            "title": snippet.get("title", ""),
            "views": self._safe_int(statistics.get("viewCount")),
            "upload_time": parse_iso_datetime(snippet.get("publishedAt")),
            "duration_seconds": duration_seconds,
            "description": snippet.get("description"),
            "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url")
            or snippet.get("thumbnails", {}).get("default", {}).get("url"),
            "subscriber_count": subscriber_count,
            "collected_at": datetime.now(timezone.utc),
            "raw_payload": item,
        }

        existing = self.video_snapshot_repository.get_one_by(
            snapshot_id=snapshot_id, competitor_video_id=data["competitor_video_id"], collected_at=data["collected_at"]
        )
        if existing is not None:
            return self.video_snapshot_repository.update(existing, **data)
        return self.video_snapshot_repository.create(**data)

    def _safe_int(self, value: Any) -> int | None:
        """Convert a possibly missing string value into an integer."""

        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _parse_duration(self, duration: str) -> int | None:
        """Convert an ISO 8601 duration string into seconds."""

        import re

        if not duration:
            return None
        pattern = re.compile(r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$")
        match = pattern.match(duration)
        if not match:
            return None
        days = int(match.group("days") or 0)
        hours = int(match.group("hours") or 0)
        minutes = int(match.group("minutes") or 0)
        seconds = int(match.group("seconds") or 0)
        return days * 86400 + hours * 3600 + minutes * 60 + seconds
