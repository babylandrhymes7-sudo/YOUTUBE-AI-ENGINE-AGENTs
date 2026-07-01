"""News-only API routes.

These endpoints are separate from YouTube channel report endpoints. News routes
collect web/news sources, run local AI analysis, and notify about latest updates.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.news_flow import run_news_alert_flow
from database.session import get_db_session


router = APIRouter(prefix="/news", tags=["news"])


class NewsAlertRequest(BaseModel):
    """Options for one news update run."""

    send_notification: bool = True


@router.post("/collect-and-alert")
async def collect_analyze_and_notify_news(
    payload: NewsAlertRequest,
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Collect web news, analyze with local AI, and send a news update notification."""

    result = await run_news_alert_flow(session, send_notification=payload.send_notification)
    return {
        "collection_stats": result.collection_stats,
        "analysis": result.analysis,
        "notification": result.notification,
        "generation_seconds": result.generation_seconds,
    }
