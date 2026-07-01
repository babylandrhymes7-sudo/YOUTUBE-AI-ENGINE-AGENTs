"""News-only collection, AI analysis, and notification orchestration.

This flow is intentionally separate from YouTube channel analytics/reporting.
It collects web/news sources, asks the local AI layer to analyze those updates,
and sends a lightweight news update notification. It does not generate channel
reports or PDFs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ai import AIEngine, create_qwen_engine
from ai.contracts import KnowledgeContext
from app.config import settings
from app.logging import get_logger
from collectors.news.engine import NewsCollectionEngine
from collectors.news.models import NewsSourceDefinition
from database.models import News
from notifications import NotificationEngine


logger = get_logger(__name__)


class NewsAnalyzer(Protocol):
    """Analyze structured news updates with a local AI model."""

    async def analyze(self, knowledge: KnowledgeContext | dict[str, Any]) -> dict[str, Any]:
        """Return structured AI analysis for notification."""


@dataclass(frozen=True)
class NewsAlertFlowResult:
    """Result from one news-only update run."""

    collection_stats: dict[str, Any]
    analysis: dict[str, Any]
    notification: dict[str, Any] | None
    generation_seconds: float


def load_news_sources(path: str | Path) -> list[NewsSourceDefinition]:
    """Load news source definitions from local JSON config."""

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"News source config not found: {config_path}")
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw_sources = raw.get("sources", [])
    elif isinstance(raw, list):
        raw_sources = raw
    else:
        raise ValueError("News source config must be an object or list")
    if not isinstance(raw_sources, list):
        raise ValueError("News source config 'sources' must be a list")
    return [NewsSourceDefinition(**item) for item in raw_sources if isinstance(item, dict)]


class NewsAlertFlow:
    """Run web/news collection -> local AI analysis -> news notification."""

    def __init__(
        self,
        collection_engine: NewsCollectionEngine,
        analyzer: NewsAnalyzer,
        notification_engine: NotificationEngine | None = None,
        *,
        max_articles: int = 10,
    ) -> None:
        self._collection_engine = collection_engine
        self._analyzer = analyzer
        self._notification_engine = notification_engine
        self._max_articles = max(1, max_articles)

    async def run(self, *, send_notification: bool = True) -> NewsAlertFlowResult:
        """Collect latest news, analyze it locally, and optionally notify."""

        started = perf_counter()
        collection_stats = self._collection_engine.collect()
        articles = self._latest_articles()
        knowledge = KnowledgeContext(
            news_intelligence={
                "collection_stats": collection_stats,
                "articles": articles,
                "purpose": "latest_web_news_update",
            },
            metadata={"flow": "news_alert"},
        )
        analysis = await self._analyzer.analyze(knowledge)
        analysis = self._normalize_analysis(analysis, articles, collection_stats)
        notification_payload: dict[str, Any] | None = None
        if send_notification and self._notification_engine is not None:
            outcome = self._notification_engine.send_news_update(analysis)
            notification_payload = outcome.to_dict()
        elapsed = perf_counter() - started
        logger.info(
            "News alert flow completed articles=%s notified=%s duration=%.3fs",
            len(articles),
            bool(notification_payload and notification_payload.get("delivered")),
            elapsed,
        )
        return NewsAlertFlowResult(
            collection_stats=collection_stats,
            analysis=analysis,
            notification=notification_payload,
            generation_seconds=elapsed,
        )

    def _latest_articles(self) -> list[dict[str, Any]]:
        statement = (
            select(News)
            .where(News.is_duplicate.is_(False))
            .order_by(desc(News.published_at), desc(News.created_at))
            .limit(self._max_articles)
        )
        rows = list(self._collection_engine.session.scalars(statement))
        return [
            {
                "title": row.title,
                "summary": row.summary,
                "url": row.url,
                "source_name": row.source_name,
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "category": row.category,
                "keywords": row.keywords or [],
                "tags": row.tags or [],
            }
            for row in rows
        ]

    def _normalize_analysis(
        self,
        analysis: dict[str, Any],
        articles: list[dict[str, Any]],
        collection_stats: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(analysis) if isinstance(analysis, dict) else {}
        normalized.setdefault("summary", normalized.get("executive_summary") or "Latest news has been analyzed.")
        normalized.setdefault("articles", articles)
        normalized.setdefault("collection_stats", collection_stats)
        normalized.setdefault("confidence", normalized.get("confidence_scores", {}).get("overall", 0.0) if isinstance(normalized.get("confidence_scores"), dict) else 0.0)
        normalized["flow"] = "news_alert"
        return normalized


def build_news_alert_flow(session: Session) -> NewsAlertFlow:
    """Build the production news-only alert flow."""

    sources = load_news_sources(settings.news_sources_config_path)
    collection_engine = NewsCollectionEngine(
        session,
        sources=sources,
        storage_root=settings.storage_paths["cache"] / "news",
    )
    return NewsAlertFlow(
        collection_engine=collection_engine,
        analyzer=create_qwen_engine(),
        notification_engine=NotificationEngine(),
    )


async def run_news_alert_flow(session: Session, *, send_notification: bool = True) -> NewsAlertFlowResult:
    """Run the production local news alert flow."""

    flow = build_news_alert_flow(session)
    try:
        return await flow.run(send_notification=send_notification)
    finally:
        analyzer = flow._analyzer
        if isinstance(analyzer, AIEngine):
            await analyzer.close()
        flow._collection_engine.close()
