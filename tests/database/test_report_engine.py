"""Comprehensive Report Engine unit tests with an isolated repository double."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from reports.contracts import ReportRequest, ReportSearchQuery
from reports.engine import ReportEngine
from reports.validator import ReportValidationError


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
        self.rows = {}
        self.sections = {}

    def create_report(self, **data):
        row = SimpleNamespace(**data)
        self.rows[row.id] = row
        return row

    def create_sections(self, report_id, sections, created_at):
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

    def get_report(self, report_id):
        try:
            report_id = uuid.UUID(str(report_id))
        except ValueError:
            return None
        return self.rows.get(report_id)

    def get_sections(self, report_id, section_keys=None):
        rows = self.sections.get(uuid.UUID(str(report_id)), [])
        return [row for row in rows if not section_keys or row.section_key in section_keys]

    def latest_version(self, logical_id):
        rows = [row for row in self.rows.values() if str(row.logical_id) == str(logical_id)]
        return max(rows, key=lambda row: row.version) if rows else None

    def search(self, query):
        rows = list(self.rows.values())
        if query.latest_versions_only:
            latest = {}
            for row in rows:
                if row.logical_id not in latest or row.version > latest[row.logical_id].version:
                    latest[row.logical_id] = row
            rows = list(latest.values())
        for name in ("video_id", "game", "topic", "category", "report_type"):
            value = getattr(query, name)
            if value is not None:
                rows = [row for row in rows if getattr(row, name) == value]
        if query.week is not None:
            rows = [row for row in rows if row.calendar_week == query.week]
        if query.month is not None:
            rows = [row for row in rows if row.calendar_month == query.month]
        if not query.include_archived:
            rows = [row for row in rows if not row.is_archived]
        total = len(rows)
        start = (query.page - 1) * query.page_size
        return rows[start : start + query.page_size], total

    def latest(self, report_type=None):
        rows = [row for row in self.rows.values() if not row.is_archived]
        if report_type:
            rows = [row for row in rows if row.report_type == report_type]
        return max(rows, key=lambda row: row.generated_at) if rows else None

    def history(self, logical_id, offset=0, limit=100):
        rows = [row for row in self.rows.values() if str(row.logical_id) == str(logical_id)]
        return sorted(rows, key=lambda row: row.version, reverse=True)[offset : offset + limit]


@pytest.fixture
def engine():
    session = FakeSession()
    repository = FakeReportRepository()
    return ReportEngine(session, repository=repository), session


def complete_sources():
    return {
        "analytics": {
            "summary": {"views": 5000},
            "overall_performance": {"trend": "up"},
            "latest_upload_analysis": {"video_id": "video-1"},
            "scores": {
                "channel_health": 80,
                "growth": 75,
                "consistency": 70,
                "packaging": 85,
                "content_quality": 82,
                "audience_health": 78,
            },
        },
        "graph_intelligence": {
            "summary": {"dominant_pattern": "evergreen_growth"},
            "retention_analysis": {"largest_drop": "00:30"},
            "ctr_analysis": {"trend": "stable"},
        },
        "competitors": {"analysis": [{"name": "Competitor A"}]},
        "news": {"summary": [{"topic": "Game update"}], "trending_topics": ["Kenji"]},
        "predictions": {"summary": [{"metric": "views"}], "confidence": 0.8},
        "ai_intelligence": {
            "executive_summary": "The channel is growing.",
            "action_plan": [
                {"title": "Low priority", "priority": "low"},
                {"title": "High priority", "priority": "high"},
                {"title": "High priority", "priority": "high"},
            ],
            "video_ideas": [{"title": "Kenji guide"}],
            "thumbnail_ideas": [{"hook": "New build"}],
            "title_suggestions": [{"title": "Best Kenji Build"}],
            "seo_suggestions": [{"keyword": "kenji"}],
            "growth_opportunities": [{"title": "Search traffic"}],
            "confidence_scores": {"overall": 0.9},
        },
    }


def test_daily_report_generation_and_storage(engine) -> None:
    report_engine, session = engine

    report = report_engine.generate_daily_report(
        complete_sources(),
        video_id="video-1",
        game="Brawl Stars",
        topic="Kenji",
    )

    assert report["report_type"] == "daily"
    assert report["version"] == 1
    assert report["document"]["executive_summary"]["data"] == "The channel is growing."
    assert report["scores"]["channel_health_score"] == 80
    assert session.commits == 1


def test_weekly_and_monthly_generation_use_same_schema(engine) -> None:
    report_engine, _ = engine
    weekly = report_engine.generate_weekly_report(complete_sources())
    monthly = report_engine.generate_monthly_report(complete_sources())

    assert set(weekly["document"]) == set(monthly["document"])
    assert weekly["report_type"] == "weekly"
    assert monthly["report_type"] == "monthly"


def test_custom_historical_and_comparison_types(engine) -> None:
    report_engine, _ = engine

    custom = report_engine.generate_custom_report(complete_sources())
    historical = report_engine.generate_historical_report(complete_sources())
    comparison = report_engine.generate_comparison_report(complete_sources())

    assert [custom["report_type"], historical["report_type"], comparison["report_type"]] == [
        "custom",
        "historical",
        "comparison",
    ]


def test_missing_and_malformed_sources_do_not_crash(engine) -> None:
    report_engine, _ = engine

    report = report_engine.generate_daily_report(
        {"analytics": "malformed", "future_engine": {"custom": True}}
    )

    assert report["document"]["channel_analytics_summary"]["status"] == "unavailable"
    assert report["document"]["appendix"]["status"] == "available"
    assert report["warnings"]


def test_action_items_are_deduplicated_and_prioritized(engine) -> None:
    report_engine, _ = engine
    report = report_engine.generate_daily_report(complete_sources())

    actions = report["document"]["action_plan"]["data"]
    assert len(actions) == 2
    assert actions[0]["priority"] == "high"


def test_report_versioning_and_history(engine) -> None:
    report_engine, _ = engine
    first = report_engine.generate_daily_report(complete_sources())
    second = report_engine.generate_report(
        ReportRequest(report_type="daily", sources=complete_sources()),
        logical_id=first["logical_id"],
    )

    history = report_engine.get_report_history(first["logical_id"])
    assert second["version"] == 2
    assert [row["version"] for row in history["items"]] == [2, 1]


def test_search_and_latest_report(engine) -> None:
    report_engine, _ = engine
    report_engine.generate_daily_report(complete_sources(), game="Brawl Stars")
    report_engine.generate_weekly_report(complete_sources(), game="Minecraft")

    result = report_engine.search_reports(
        ReportSearchQuery(game="Brawl Stars", report_type="daily")
    )
    latest = report_engine.get_latest_report("weekly")

    assert result["pagination"]["total"] == 1
    assert latest["game"] == "Minecraft"


def test_report_comparison_returns_score_changes(engine) -> None:
    report_engine, _ = engine
    left = report_engine.generate_daily_report(complete_sources())
    changed = complete_sources()
    changed["analytics"]["scores"]["growth"] = 95
    right = report_engine.generate_daily_report(changed)

    comparison = report_engine.compare_reports(left["report_id"], right["report_id"])
    assert comparison["score_comparison"]["growth_score"]["change"] == 20


def test_selected_sections_can_be_loaded_lazily(engine) -> None:
    report_engine, _ = engine
    report = report_engine.generate_daily_report(complete_sources())

    loaded = report_engine.load_report(
        report["report_id"], include_document=False, section_keys=["action_plan"]
    )
    assert "document" not in loaded
    assert list(loaded["sections"]) == ["action_plan"]


def test_invalid_report_metadata_is_rejected(engine) -> None:
    report_engine, _ = engine
    with pytest.raises(ReportValidationError):
        report_engine.generate_report(
            ReportRequest(report_type="hourly", sources={})
        )
