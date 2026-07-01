"""Local queue persistence for failed notifications."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class QueuedNotification:
    notification_id: str
    provider: str
    payload: dict[str, Any]
    attempts: int = 0
    next_retry_at: str | None = None


class NotificationQueue:
    def __init__(self, queue_path: Path) -> None:
        self._queue_path = queue_path
        self._queue_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[QueuedNotification]:
        if not self._queue_path.exists():
            return []
        try:
            raw = json.loads(self._queue_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        items: list[QueuedNotification] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                items.append(
                    QueuedNotification(
                        notification_id=str(item["notification_id"]),
                        provider=str(item["provider"]),
                        payload=dict(item["payload"]),
                        attempts=int(item.get("attempts", 0)),
                        next_retry_at=item.get("next_retry_at"),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return items

    def save(self, items: list[QueuedNotification]) -> None:
        payload = [
            {
                "notification_id": item.notification_id,
                "provider": item.provider,
                "payload": item.payload,
                "attempts": item.attempts,
                "next_retry_at": item.next_retry_at,
            }
            for item in items
        ]
        self._queue_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def enqueue(self, item: QueuedNotification) -> None:
        items = self.load()
        if any(existing.notification_id == item.notification_id and existing.provider == item.provider for existing in items):
            return
        items.append(item)
        self.save(items)

    def dequeue_ready(self) -> list[QueuedNotification]:
        now = datetime.now(timezone.utc)
        items = self.load()
        ready: list[QueuedNotification] = []
        remaining: list[QueuedNotification] = []
        for item in items:
            if item.next_retry_at is None:
                ready.append(item)
                continue
            try:
                retry_at = datetime.fromisoformat(item.next_retry_at)
            except ValueError:
                ready.append(item)
                continue
            if retry_at <= now:
                ready.append(item)
            else:
                remaining.append(item)
        self.save(remaining)
        return ready
