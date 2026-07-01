"""OAuth helpers for the local YouTube collection engine.

TODO: Keep OAuth token refresh and authorization-code exchange local and explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.logging import get_logger


logger = get_logger(__name__)

YOUTUBE_SCOPES = (
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
)


@dataclass(frozen=True)
class OAuthToken:
    """Represent an access token returned by Google's OAuth server."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None


class YouTubeOAuthManager:
    """Handle OAuth 2.0 token refresh and optional auth-code exchange."""

    def __init__(self) -> None:
        """Store the environment-backed OAuth configuration."""

        self.client_id = settings.youtube_oauth_client_id
        self.client_secret = settings.youtube_oauth_client_secret
        self.refresh_token = settings.youtube_oauth_refresh_token
        self.access_token = settings.youtube_oauth_access_token
        self.token_uri = settings.youtube_oauth_token_uri
        self.redirect_uri = settings.youtube_oauth_redirect_uri

    def get_access_token(self) -> str:
        """Return a bearer token using the configured OAuth credentials."""

        if self.access_token:
            return self.access_token
        if self.refresh_token:
            token = self.refresh_access_token()
            self.access_token = token.access_token
            return token.access_token
        raise ValueError("YouTube OAuth credentials are not configured.")

    def refresh_access_token(self) -> OAuthToken:
        """Refresh the OAuth access token using the configured refresh token."""

        if not self.client_id or not self.client_secret or not self.refresh_token:
            raise ValueError("YouTube OAuth refresh flow requires client ID, secret, and refresh token.")

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }
        response = httpx.post(self.token_uri, data=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        logger.info("Refreshed YouTube OAuth access token")
        return OAuthToken(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in"),
            refresh_token=data.get("refresh_token"),
        )

    def exchange_authorization_code(self, authorization_code: str) -> OAuthToken:
        """Exchange an OAuth authorization code for a usable access token."""

        if not self.client_id or not self.client_secret:
            raise ValueError("YouTube OAuth authorization flow requires client ID and secret.")

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": authorization_code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        response = httpx.post(self.token_uri, data=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        logger.info("Exchanged YouTube OAuth authorization code")
        return OAuthToken(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in"),
            refresh_token=data.get("refresh_token"),
        )

    def build_authorization_url(self, state: str | None = None) -> str:
        """Build the consent URL for a one-time manual OAuth authorization flow."""

        if not self.client_id:
            raise ValueError("YouTube OAuth client ID is required to build an authorization URL.")

        query = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(YOUTUBE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            query["state"] = state
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(query)}"
