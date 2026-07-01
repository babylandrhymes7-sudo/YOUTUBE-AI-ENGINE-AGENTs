"""Unit tests for the notification engine and providers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from notifications import AlertManager, NotificationCategory, NotificationEngine, NotificationMessage, NotificationPriority, NotificationProvider, build_notification_engine
from notifications.contracts import NotificationAttachment, NotificationChannel, NotificationDeliveryResult
from notifications.manager import NotificationManager, NotificationValidationError
from notifications.queue import NotificationQueue
from notifications.retry import RetryManager


@dataclass
class FakeProvider:
    name: str
    should_fail: bool = False
    deliveries: list[NotificationMessage] | None = None

    def send(self, message: NotificationMessage) -> NotificationDeliveryResult:
        if self.deliveries is not None:
            self.deliveries.append(message)
        if self.should_fail:
            return NotificationDeliveryResult(
                provider=self.name,
                channel=NotificationChannel.TELEGRAM,
                notification_id=message.notification_id,
                success=False,
                error="boom",
            )
        return NotificationDeliveryResult(
            provider=self.name,
            channel=NotificationChannel.TELEGRAM,
            notification_id=message.notification_id,
            success=True,
            attachment_sent=bool(message.attachments),
            recipient=self.name,
        )


def _daily_report() -> dict:
    return {
        "report_type": "daily",
        "report_id": "report-1",
        "version": 1,
        "document": {
            "executive_summary": {"data": "Channel is growing."},
            "action_plan": {"data": [{"title": "Publish sooner", "priority": "high"}]},
            "video_ideas": {"data": [{"title": "Kenji guide"}]},
            "growth_opportunities": {"data": [{"title": "Trend overlap"}]},
            "threats": {"data": [{"title": "Retention dip"}]},
            "confidence_scores": {"overall": 0.91},
        },
        "scores": {"channel_health_score": 88},
        "metadata": {"best_upload_time_today": "18:00", "report_generation_time_seconds": 4.2},
    }


def _weekly_report() -> dict:
    report = _daily_report()
    report["report_type"] = "weekly"
    return report


def test_daily_brief_builds_notification_and_attaches_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "daily.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")
    deliveries: list[NotificationMessage] = []
    manager = NotificationManager([FakeProvider("telegram", deliveries=deliveries)])

    outcome = manager.send_daily_brief(_daily_report(), pdf_path, generation_seconds=2.5)

    assert outcome.delivered is True
    assert outcome.category is NotificationCategory.DAILY_MORNING_BRIEF
    assert deliveries[0].attachments[0].path == pdf_path
    assert "Channel Health Score" in deliveries[0].body
    assert deliveries[0].confidence == pytest.approx(0.91)


def test_weekly_brief_uses_weekly_category(tmp_path: Path) -> None:
    pdf_path = tmp_path / "weekly.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")
    manager = NotificationManager([FakeProvider("telegram")])

    outcome = manager.send_weekly_brief(_weekly_report(), pdf_path)

    assert outcome.category is NotificationCategory.WEEKLY_STRATEGY_BRIEF
    assert outcome.delivered is True


def test_instant_alert_is_filtered_below_threshold() -> None:
    manager = NotificationManager([FakeProvider("telegram")])

    outcome = manager.send_instant_alert({"confidence": 0.2, "priority": "low", "description": "small change"})

    assert outcome.delivered is False
    assert outcome.skipped_reason


def test_instant_alert_emits_high_priority_message() -> None:
    manager = NotificationManager([FakeProvider("telegram")])

    outcome = manager.send_instant_alert(
        {
            "confidence": 0.97,
            "priority": "urgent",
            "impact": 0.8,
            "delta_percent": 31,
            "what_happened": "Brawl Stars released balance changes.",
            "why_it_matters": "Your competitor topics match this update.",
            "expected_impact": "Likely to increase clicks.",
            "recommended_action": "Publish within six hours.",
        }
    )

    assert outcome.delivered is True
    assert outcome.provider_results[0].success is True


def test_duplicate_notification_is_skipped(tmp_path: Path) -> None:
    ledger = tmp_path / "sent.json"
    manager = NotificationManager([FakeProvider("telegram")], sent_ledger_path=ledger)
    report = _daily_report()

    first = manager.send_daily_brief(report, tmp_path / "daily.pdf")
    second = manager.send_daily_brief(report, tmp_path / "daily.pdf")

    assert first.delivered is True
    assert second.delivered is False
    assert second.skipped_reason == "duplicate notification"


def test_missing_pdf_queues_attachment_retry(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.json"
    queue = NotificationQueue(queue_path)
    manager = NotificationManager([FakeProvider("telegram")], queue=queue)

    outcome = manager.send_daily_brief(_daily_report(), tmp_path / "missing.pdf")

    assert outcome.delivered is True
    assert outcome.queued is True
    assert queue_path.exists()
    assert queue.load()


def test_provider_failure_does_not_raise(tmp_path: Path) -> None:
    manager = NotificationManager([FakeProvider("telegram", should_fail=True)])

    outcome = manager.send_daily_brief(_daily_report(), tmp_path / "daily.pdf")

    assert outcome.delivered is False
    assert outcome.provider_results[0].success is False


def test_alert_manager_builds_executable_message() -> None:
    decision = AlertManager().evaluate(
        {
            "confidence": 0.96,
            "priority": "high",
            "impact": 0.8,
            "delta_percent": 25,
            "what_happened": "GTA VI news landed.",
            "why_it_matters": "This overlaps with your best historical content.",
            "expected_impact": "High click potential.",
            "recommended_action": "Create coverage today.",
        }
    )

    assert decision.should_notify is True
    assert decision.message is not None
    assert decision.message.category is NotificationCategory.INSTANT_AI_ALERT


def test_notification_engine_facade_builds_manager() -> None:
    engine = NotificationEngine(build_notification_engine())
    assert engine is not None


def test_invalid_report_type_is_rejected() -> None:
    manager = NotificationManager([FakeProvider("telegram")])

    with pytest.raises(NotificationValidationError):
        manager.send_daily_brief({"report_type": "weekly"}, None)
