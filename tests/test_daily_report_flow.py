"""End-to-end local daily flow test using mocked structured inputs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from app.daily_flow import DailyReportFlow
from notifications import NotificationEngine, NotificationManager, NotificationMessage
from notifications.contracts import NotificationChannel, NotificationDeliveryResult
from notifications.queue import NotificationQueue
from pdf import PDFEngine
from reports import ReportEngine


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeReportRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, SimpleNamespace] = {}
        self.sections: dict[uuid.UUID, list[SimpleNamespace]] = {}

    def create_report(self, **data):
        row = SimpleNamespace(**data)
        self.rows[row.id] = row
        return row

    def create_sections(self, report_id, sections, created_at) -> None:
        self.sections[report_id] = [
            SimpleNamespace(
                section_key=key,
                available=value["status"] == "available",
                importance=value["importance"],
                payload_json=value["data"],
                warnings_json=value["warnings"],
            )
            for key, value in sections.items()
        ]

    def latest_version(self, logical_id):
        rows = [row for row in self.rows.values() if str(row.logical_id) == str(logical_id)]
        return max(rows, key=lambda row: row.version) if rows else None


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
            attachment_sent=bool(message.attachments),
            recipient="local-test",
        )


def structured_sources() -> dict:
    return {
        "analytics": {
            "summary": {"views": 7500, "watch_time_hours": 420},
            "overall_performance": {"trend": "up"},
            "latest_upload_analysis": {
                "title": "Kenji Guide",
                "views": 1200,
                "ctr": "8.4%",
                "retention": "47%",
                "worked": "Strong search intent.",
                "failed": "First 30 seconds dipped.",
                "improvement": "Open with final build reveal.",
            },
            "scores": {
                "channel_health": 84,
                "growth": 81,
                "consistency": 72,
                "packaging": 88,
                "content_quality": 80,
                "audience_health": 79,
            },
        },
        "graph_intelligence": {
            "summary": {"dominant_pattern": "evergreen_growth"},
            "retention_analysis": {"largest_drop": "00:30"},
            "ctr_analysis": {"trend": "stable"},
        },
        "news": {"summary": [{"topic": "Brawl Stars balance update"}], "trending_topics": ["Kenji"]},
        "predictions": {"summary": [{"metric": "views", "prediction": "higher"}], "confidence": 0.82},
        "ai_intelligence": {
            "executive_summary": "Channel is growing and packaging is the highest leverage area.",
            "action_plan": [{"title": "Refresh Kenji thumbnails", "priority": "high", "confidence": 0.91}],
            "video_ideas": [{"title": "Best Kenji Build After Update", "hook": "New meta build"}],
            "thumbnail_ideas": [{"hook": "Before vs after build"}],
            "title_suggestions": [{"title": "This Kenji Build Is Broken"}],
            "seo_suggestions": [{"keyword": "kenji build"}],
            "growth_opportunities": [{"title": "Search demand is rising"}],
            "confidence_scores": {"overall": 0.9},
        },
    }


def test_daily_flow_generates_report_pdf_and_notification(tmp_path: Path) -> None:
    session = FakeSession()
    report_engine = ReportEngine(session, repository=FakeReportRepository())
    pdf_engine = PDFEngine(output_dir=tmp_path / "reports")
    deliveries: list[NotificationMessage] = []
    manager = NotificationManager(
        [FakeProvider("telegram", deliveries)],
        queue=NotificationQueue(tmp_path / "queue.json"),
        sent_ledger_path=tmp_path / "sent.json",
    )
    flow = DailyReportFlow(report_engine, pdf_engine, NotificationEngine(manager))

    result = flow.run(
        structured_sources(),
        report_kwargs={"game": "Brawl Stars", "topic": "Kenji", "video_id": "video-1"},
    )

    assert result.report["report_type"] == "daily"
    assert result.report["document"]["executive_summary"]["status"] == "available"
    assert result.pdf_path.exists()
    assert result.notification is not None
    assert result.notification["delivered"] is True
    assert deliveries[0].attachments[0].path == result.pdf_path
    assert session.commits == 1
