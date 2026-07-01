"""Application settings and path configuration.

TODO: Keep this module focused on environment parsing and runtime paths.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from the environment.

    TODO: Extend this schema with module-specific settings as the codebase grows.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="YOUTUBE AI AGENT")
    app_env: str = Field(default="development")
    app_host: str = Field(default="127.0.0.1")
    app_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")
    log_dir: str = Field(default="logs")
    scheduler_enabled: bool = Field(default=True)
    scheduler_timezone: str = Field(default="America/New_York")
    scheduler_every_30_minutes: int = Field(default=30)
    daily_report_hour: int = Field(default=8)
    daily_report_minute: int = Field(default=0)
    weekly_report_day_of_week: str = Field(default="sun")
    weekly_report_hour: int = Field(default=8)
    weekly_report_minute: int = Field(default=0)
    monthly_report_day: int = Field(default=1)
    monthly_report_hour: int = Field(default=8)
    monthly_report_minute: int = Field(default=0)
    scheduler_retry_attempts: int = Field(default=3)
    scheduler_retry_delay_seconds: int = Field(default=30)
    database_url: str = Field(default="postgresql+psycopg2://postgres:postgres@localhost:5432/youtube_ai_agent")
    youtube_api_base_url: str = Field(default="https://www.googleapis.com/youtube/v3")
    youtube_analytics_base_url: str = Field(default="https://youtubeanalytics.googleapis.com/v2")
    youtube_oauth_client_id: str = Field(default="")
    youtube_oauth_client_secret: str = Field(default="")
    youtube_oauth_refresh_token: str = Field(default="")
    youtube_oauth_access_token: str = Field(default="")
    youtube_oauth_token_uri: str = Field(default="https://oauth2.googleapis.com/token")
    youtube_oauth_redirect_uri: str = Field(default="http://localhost:8000/auth/youtube/callback")
    youtube_analytics_ids: str = Field(default="channel==MINE")
    youtube_requests_per_minute: int = Field(default=60)
    youtube_retry_attempts: int = Field(default=3)
    youtube_retry_delay_seconds: int = Field(default=10)
    youtube_api_key: str = Field(default="")
    news_api_key: str = Field(default="")
    competitor_channel_ids: str = Field(default="")
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")
    email_sender: str = Field(default="notifications@localhost")
    email_recipients: str = Field(default="")
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=587)
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_use_tls: bool = Field(default=True)
    notification_enabled_providers: str = Field(default="telegram,email,desktop")
    notification_daily_time: str = Field(default="08:00")
    notification_weekly_day_of_week: str = Field(default="sun")
    notification_weekly_time: str = Field(default="08:30")
    notification_retry_attempts: int = Field(default=3)
    notification_retry_delay_seconds: int = Field(default=30)
    notification_max_attachment_size_mb: int = Field(default=25)
    notification_quiet_hours_start: str = Field(default="22:00")
    notification_quiet_hours_end: str = Field(default="07:00")
    notification_priority_filters: str = Field(default="urgent,high")
    notification_state_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[1] / "storage" / "cache" / "notifications")
    instant_alert_min_confidence: float = Field(default=0.85)
    instant_alert_min_impact: float = Field(default=0.65)
    instant_alert_min_delta_percent: float = Field(default=15.0)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="qwen3.5")
    ollama_timeout_seconds: float = Field(default=120.0)
    ollama_retry_attempts: int = Field(default=2)
    ollama_retry_delay_seconds: float = Field(default=1.0)
    storage_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[1] / "storage")
    prefer_local_storage: bool = Field(default=True)
    download_only_when_needed: bool = Field(default=True)
    daily_report_source_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1] / "storage" / "cache" / "daily_report_sources.json"
    )
    weekly_report_source_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1] / "storage" / "cache" / "weekly_report_sources.json"
    )
    monthly_report_source_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1] / "storage" / "cache" / "monthly_report_sources.json"
    )
    news_sources_config_path: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[1] / "config" / "rss.json")

    @property
    def storage_paths(self) -> dict[str, Path]:
        """Return the standard local storage paths used by the project."""

        return {
            "root": self.storage_root,
            "thumbnails": self.storage_root / "thumbnails",
            "reports": self.storage_root / "reports",
            "graphs": self.storage_root / "graphs",
            "screenshots": self.storage_root / "screenshots",
            "cache": self.storage_root / "cache",
            "backups": self.storage_root / "backups",
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings instance."""

    return Settings()


settings = get_settings()
