"""Reports API routes for local canonical report orchestration."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.daily_flow import build_daily_report_flow
from database.session import get_db_session
from reports import ReportEngine, ReportSearchQuery


router = APIRouter(prefix="/reports", tags=["reports"])


class DailyReportRequest(BaseModel):
    """Structured subsystem outputs for one daily report."""

    sources: dict[str, Any] = Field(default_factory=dict)
    send_notification: bool = True
    channel_id: str | None = None
    video_id: str | None = None
    game: str | None = None
    topic: str | None = None
    category: str | None = None


class ReportSearchRequest(BaseModel):
    """Search filters for canonical reports."""

    report_type: str | None = None
    video_id: str | None = None
    game: str | None = None
    topic: str | None = None
    category: str | None = None
    page: int = 1
    page_size: int = 50


@router.post("/daily")
def generate_daily_report(payload: DailyReportRequest, session: Session = Depends(get_db_session)) -> dict[str, Any]:
    """Generate and store canonical daily report JSON only."""

    engine = ReportEngine(session)
    return engine.generate_daily_report(
        payload.sources,
        channel_id=payload.channel_id,
        video_id=payload.video_id,
        game=payload.game,
        topic=payload.topic,
        category=payload.category,
    )


@router.post("/daily/full-flow")
def run_daily_report_flow(payload: DailyReportRequest, session: Session = Depends(get_db_session)) -> dict[str, Any]:
    """Run Report -> PDF -> Notification using structured local JSON."""

    result = build_daily_report_flow(session).run(
        payload.sources,
        send_notification=payload.send_notification,
        report_kwargs={
            "channel_id": payload.channel_id,
            "video_id": payload.video_id,
            "game": payload.game,
            "topic": payload.topic,
            "category": payload.category,
        },
    )
    return {
        "report": result.report,
        "pdf_path": str(result.pdf_path),
        "notification": result.notification,
        "generation_seconds": result.generation_seconds,
    }


@router.post("/{report_type}/full-flow")
def run_channel_report_flow(report_type: str, payload: DailyReportRequest, session: Session = Depends(get_db_session)) -> dict[str, Any]:
    """Run daily, weekly, or monthly YouTube channel Report -> PDF -> Notification."""

    if report_type not in {"daily", "weekly", "monthly"}:
        raise HTTPException(status_code=400, detail="report_type must be daily, weekly, or monthly")
    result = build_daily_report_flow(session).run(
        payload.sources,
        report_type=report_type,
        send_notification=payload.send_notification,
        report_kwargs={
            "channel_id": payload.channel_id,
            "video_id": payload.video_id,
            "game": payload.game,
            "topic": payload.topic,
            "category": payload.category,
        },
    )
    return {
        "report": result.report,
        "pdf_path": str(result.pdf_path),
        "notification": result.notification,
        "generation_seconds": result.generation_seconds,
    }


@router.post("/search")
def search_reports(payload: ReportSearchRequest, session: Session = Depends(get_db_session)) -> dict[str, Any]:
    """Search report history without rendering reports."""

    return ReportEngine(session).search_reports(ReportSearchQuery(**payload.model_dump()))


@router.get("/latest/{report_type}")
def latest_report(report_type: str, session: Session = Depends(get_db_session)) -> dict[str, Any] | None:
    """Return the latest canonical report of a type."""

    return ReportEngine(session).get_latest_report(report_type)
