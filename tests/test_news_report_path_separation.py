"""Verify news alerts and YouTube report notifications stay on separate paths."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.news_flow import NewsAlertFlow
from notifications import NotificationCategory, NotificationEngine, NotificationManager, NotificationMessage
from notifications.contracts import NotificationChannel, NotificationDeliveryResult
from notifications.queue import NotificationQueue


@dataclass
class FakeProvider:
    name: str
    deliveries: list[NotificationMessage]

    def send(self, message: NotificationMessage) -> NotificationDeliveryResult:
        self.deliveries.append(message)
        return NotificationDeliveryResult(
            provider=self.name,
            channel=NotificationChannel.TELEGRAM,
            notification_id=message.notification_id,
            success=True,
        )


class FakeNewsSession:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self, statement: Any) -> list[Any]:
        return self._rows


class FakeNewsCollector:
    def __init__(self, rows: list[Any]) -> None:
        self.session = FakeNewsSession(rows)
        self.collect_calls = 0

    def collect(self) -> dict[str, int]:
        self.collect_calls += 1
        return {"sources": 1, "articles": len(self.session._rows), "duplicates": 0, "stored_files": 0}


class FakeNewsAnalyzer:
    def __init__(self) -> None:
        self.received: dict[str, Any] | None = None

    async def analyze(self, knowledge: Any) -> dict[str, Any]:
        self.received = knowledge.to_dict()
        return {
            "summary": "Brawl Stars balance news is trending.",
            "opportunities": [{"title": "Make a Kenji update short"}],
            "action_plan": [{"title": "Publish news reaction today"}],
            "confidence": 0.93,
        }


def test_news_flow_collects_web_news_analyzes_and_sends_news_update(tmp_path: Path) -> None:
    rows = [
        SimpleNamespace(
            title="Brawl Stars balance update",
            summary="Kenji changed in the latest update.",
            url="https://example.test/brawl-update",
            source_name="Example News",
            published_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
            category="gaming",
            keywords=["kenji"],
            tags=["brawl-stars"],
        )
    ]
    deliveries: list[NotificationMessage] = []
    manager = NotificationManager(
        [FakeProvider("telegram", deliveries)],
        queue=NotificationQueue(tmp_path / "news_queue.json"),
        sent_ledger_path=tmp_path / "news_sent.json",
    )
    analyzer = FakeNewsAnalyzer()
    flow = NewsAlertFlow(
        FakeNewsCollector(rows),  # type: ignore[arg-type]
        analyzer,
        NotificationEngine(manager),
    )

    result = asyncio.run(flow.run())

    assert result.collection_stats["articles"] == 1
    assert result.notification is not None
    assert result.notification["category"] == NotificationCategory.NEWS_UPDATE.value
    assert deliveries[0].category is NotificationCategory.NEWS_UPDATE
    assert "News Summary" in deliveries[0].body
    assert deliveries[0].attachments == ()
    assert analyzer.received is not None
    assert analyzer.received["metadata"]["flow"] == "news_alert"
