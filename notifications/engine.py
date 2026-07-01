"""High-level notification engine orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import settings

from .alerts import AlertManager
from .contracts import NotificationOutcome
from .desktop import DesktopProvider
from .email import EmailProvider
from .manager import NotificationManager
from .queue import NotificationQueue
from .retry import RetryManager
from .telegram import TelegramProvider


class NotificationEngine:
    def __init__(self, manager: NotificationManager | None = None) -> None:
        self._manager = manager or build_notification_engine()

    def send_daily_morning_brief(self, report: dict[str, Any], pdf_path: str | Path | None, *, generation_seconds: float | None = None) -> NotificationOutcome:
        return self._manager.send_daily_brief(report, pdf_path, generation_seconds=generation_seconds)

    def send_weekly_strategy_brief(self, report: dict[str, Any], pdf_path: str | Path | None, *, generation_seconds: float | None = None) -> NotificationOutcome:
        return self._manager.send_weekly_brief(report, pdf_path, generation_seconds=generation_seconds)

    def send_instant_ai_alert(self, event: dict[str, Any]) -> NotificationOutcome:
        return self._manager.send_instant_alert(event)

    def retry_failed_notifications(self) -> list[NotificationOutcome]:
        return self._manager.retry_failed()


def build_notification_engine() -> NotificationManager:
    enabled = {value.strip().lower() for value in settings.notification_enabled_providers.split(",") if value.strip()}
    providers = []
    if "telegram" in enabled:
        providers.append(TelegramProvider())
    if "email" in enabled:
        providers.append(EmailProvider())
    if "desktop" in enabled:
        providers.append(DesktopProvider())
    queue = NotificationQueue(settings.notification_state_dir / "queue.json")
    retry_manager = RetryManager(settings.notification_retry_attempts, settings.notification_retry_delay_seconds)
    alert_manager = AlertManager(
        min_confidence=settings.instant_alert_min_confidence,
        min_impact=settings.instant_alert_min_impact,
        min_delta_percent=settings.instant_alert_min_delta_percent,
    )
    return NotificationManager(providers, queue=queue, retry_manager=retry_manager, alert_manager=alert_manager)
