"""Stable notification contracts shared across providers and the engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class NotificationCategory(str, Enum):
    DAILY_MORNING_BRIEF = "daily_morning_brief"
    INSTANT_AI_ALERT = "instant_ai_alert"
    WEEKLY_STRATEGY_BRIEF = "weekly_strategy_brief"


class NotificationChannel(str, Enum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    DESKTOP = "desktop"


class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass(frozen=True)
class NotificationAttachment:
    path: Path
    filename: str | None = None
    mime_type: str = "application/octet-stream"
    sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["path"] = str(self.path)
        return payload


@dataclass(frozen=True)
class NotificationMessage:
    notification_id: str
    category: NotificationCategory
    title: str
    summary: str
    body: str
    data: dict[str, Any] = field(default_factory=dict)
    attachments: tuple[NotificationAttachment, ...] = ()
    priority: NotificationPriority = NotificationPriority.NORMAL
    confidence: float | None = None
    recipient: str | None = None
    open_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["category"] = self.category.value
        payload["priority"] = self.priority.value
        payload["attachments"] = [attachment.to_dict() for attachment in self.attachments]
        payload["open_path"] = str(self.open_path) if self.open_path else None
        return payload


@dataclass(frozen=True)
class NotificationDeliveryResult:
    provider: str
    channel: NotificationChannel
    notification_id: str
    success: bool
    retries: int = 0
    warnings: tuple[str, ...] = ()
    error: str | None = None
    attachment_sent: bool = False
    recipient: str | None = None


@dataclass(frozen=True)
class NotificationOutcome:
    notification_id: str
    category: NotificationCategory
    title: str
    delivered: bool
    provider_results: tuple[NotificationDeliveryResult, ...] = ()
    queued: bool = False
    skipped_reason: str | None = None
    warnings: tuple[str, ...] = ()
