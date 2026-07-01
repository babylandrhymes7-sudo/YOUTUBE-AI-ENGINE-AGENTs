"""Notification provider interface."""

from __future__ import annotations

from typing import Protocol

from .contracts import NotificationDeliveryResult, NotificationMessage


class NotificationProvider(Protocol):
    name: str

    def send(self, message: NotificationMessage) -> NotificationDeliveryResult:
        """Deliver one notification message through this provider."""
