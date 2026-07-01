"""HTTP client for the YouTube Data and Analytics APIs.

TODO: Keep retries, throttling, and transport concerns in this module only.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import httpx

from app.config import settings
from app.logging import get_logger

from .auth import YouTubeOAuthManager
from .rate_limiter import RateLimiter


logger = get_logger(__name__)


class YouTubeApiClient:
    """HTTP client that speaks to the YouTube Data and Analytics APIs."""

    def __init__(
        self,
        oauth_manager: YouTubeOAuthManager | None = None,
        rate_limiter: RateLimiter | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        """Initialize the client with OAuth, rate limiting, and HTTP transport."""

        self._oauth_manager = oauth_manager or YouTubeOAuthManager()
        self._rate_limiter = rate_limiter or RateLimiter(settings.youtube_requests_per_minute)
        self._client = http_client or httpx.Client(timeout=30)
        self._retry_attempts = max(1, settings.youtube_retry_attempts)
        self._retry_delay_seconds = max(1, settings.youtube_retry_delay_seconds)
        self._api_base_url = settings.youtube_api_base_url.rstrip("/")
        self._analytics_base_url = settings.youtube_analytics_base_url.rstrip("/")

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self._client.close()

    def _headers(self) -> dict[str, str]:
        """Build the authorization headers for each API request."""

        return {"Authorization": f"Bearer {self._oauth_manager.get_access_token()}", "Accept": "application/json"}

    def _request_json(
        self,
        *,
        base_url: str,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform a retried and rate-limited API request, returning parsed JSON."""

        url = f"{base_url}/{path.lstrip('/')}"
        last_error: Exception | None = None
        for attempt in range(1, self._retry_attempts + 1):
            try:
                self._rate_limiter.acquire()
                response = self._client.request(method, url, params=params, json=json_body, headers=self._headers())
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # pragma: no cover - runtime safety
                last_error = exc
                logger.exception("YouTube API request failed for {} attempt {}", url, attempt)
                if attempt < self._retry_attempts:
                    time.sleep(self._retry_delay_seconds)
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Unexpected failure requesting {url}")

    def get_channel(self, channel_id: str) -> dict[str, Any]:
        """Fetch channel metadata from the YouTube Data API."""

        return self._request_json(
            base_url=self._api_base_url,
            method="GET",
            path="channels",
            params={
                "part": "snippet,contentDetails,statistics,status,brandingSettings,topicDetails",
                "id": channel_id,
                "maxResults": 1,
            },
        )

    def get_upload_playlist_id(self, channel_id: str) -> str | None:
        """Return the uploads playlist id for a channel if it exists."""

        payload = self.get_channel(channel_id)
        items = payload.get("items", [])
        if not items:
            return None
        return items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")

    def list_playlist_items(self, playlist_id: str, page_token: str | None = None) -> dict[str, Any]:
        """List playlist items for a specific uploads playlist."""

        params: dict[str, Any] = {
            "part": "snippet,contentDetails,status",
            "playlistId": playlist_id,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token
        return self._request_json(base_url=self._api_base_url, method="GET", path="playlistItems", params=params)

    def list_videos(self, video_ids: Sequence[str]) -> dict[str, Any]:
        """Fetch detailed metadata for a batch of video ids."""

        return self._request_json(
            base_url=self._api_base_url,
            method="GET",
            path="videos",
            params={
                "part": "snippet,contentDetails,statistics,status,liveStreamingDetails,topicDetails",
                "id": ",".join(video_ids),
                "maxResults": 50,
            },
        )

    def list_comment_threads(self, video_id: str, page_token: str | None = None) -> dict[str, Any]:
        """Fetch top-level comments and replies for a video."""

        params: dict[str, Any] = {
            "part": "snippet,replies",
            "videoId": video_id,
            "maxResults": 100,
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token
        return self._request_json(base_url=self._api_base_url, method="GET", path="commentThreads", params=params)

    def query_analytics(self, **params: Any) -> dict[str, Any]:
        """Query the YouTube Analytics API for metrics and dimensions."""

        return self._request_json(base_url=self._analytics_base_url, method="GET", path="reports", params=params)
