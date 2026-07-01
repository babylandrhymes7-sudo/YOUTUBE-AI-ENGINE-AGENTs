"""Notifications package."""

from .alerts import AlertManager
from .base import NotificationProvider
from .contracts import (
	NotificationAttachment,
	NotificationCategory,
	NotificationChannel,
	NotificationDeliveryResult,
	NotificationMessage,
	NotificationOutcome,
	NotificationPriority,
)
from .desktop import DesktopProvider
from .email import EmailProvider
from .engine import NotificationEngine, build_notification_engine
from .manager import NotificationManager
from .queue import NotificationQueue
from .retry import RetryManager
from .telegram import TelegramProvider

__all__ = [
	"AlertManager",
	"DesktopProvider",
	"EmailProvider",
	"NotificationAttachment",
	"NotificationCategory",
	"NotificationChannel",
	"NotificationDeliveryResult",
	"NotificationEngine",
	"NotificationManager",
	"NotificationMessage",
	"NotificationOutcome",
	"NotificationPriority",
	"NotificationProvider",
	"NotificationQueue",
	"RetryManager",
	"TelegramProvider",
	"build_notification_engine",
]

