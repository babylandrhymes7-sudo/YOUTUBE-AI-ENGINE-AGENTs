"""Local daily report orchestration.

This module is intentionally a thin conveyor belt. It does not collect
YouTube data, calculate analytics, call AI models, or render dashboard views.
It consumes structured JSON produced elsewhere and moves it through:

Report Engine -> PDF Engine -> Notification Engine
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.config import settings
from app.logging import get_logger
from notifications import NotificationEngine
from pdf import PDFEngine
from reports import ReportEngine


logger = get_logger(__name__)


class StructuredSourceProvider(Protocol):
    """Return structured subsystem JSON ready for the Report Engine."""

    def load_daily_sources(self) -> dict[str, Any]:
        """Load already-generated local knowledge for a daily report."""


@dataclass(frozen=True)
class LocalJSONSourceProvider:
    """Load structured daily-report sources from a local JSON handoff file."""

    source_path: Path

    def load_daily_sources(self) -> dict[str, Any]:
        if not self.source_path.exists():
            raise FileNotFoundError(f"Daily report source JSON not found: {self.source_path}")
        payload = json.loads(self.source_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Daily report source JSON must be an object")
        sources = payload.get("sources", payload)
        if not isinstance(sources, dict):
            raise ValueError("Daily report sources must be an object")
        return sources


@dataclass(frozen=True)
class DailyReportFlowResult:
    """Result produced by one local daily report flow run."""

    report: dict[str, Any]
    pdf_path: Path
    notification: dict[str, Any] | None
    generation_seconds: float


class DailyReportFlow:
    """Run the local YouTube channel report handoff flow."""

    def __init__(
        self,
        report_engine: ReportEngine,
        pdf_engine: PDFEngine,
        notification_engine: NotificationEngine | None = None,
    ) -> None:
        self._report_engine = report_engine
        self._pdf_engine = pdf_engine
        self._notification_engine = notification_engine

    def run(
        self,
        sources: dict[str, Any],
        *,
        report_type: str = "daily",
        send_notification: bool = True,
        report_kwargs: dict[str, Any] | None = None,
    ) -> DailyReportFlowResult:
        """Generate, render, and optionally notify for one channel report."""

        started = perf_counter()
        if report_type == "daily":
            report = self._report_engine.generate_daily_report(sources, **(report_kwargs or {}))
        elif report_type == "weekly":
            report = self._report_engine.generate_weekly_report(sources, **(report_kwargs or {}))
        elif report_type == "monthly":
            report = self._report_engine.generate_monthly_report(sources, **(report_kwargs or {}))
        else:
            raise ValueError("report_type must be daily, weekly, or monthly")
        document = report.get("document")
        if not isinstance(document, dict):
            raise ValueError("Report Engine returned a report without canonical document JSON")

        pdf_result = self._pdf_engine.generate(document)
        elapsed = perf_counter() - started
        notification_payload: dict[str, Any] | None = None
        if send_notification and self._notification_engine is not None:
            if report_type == "daily":
                outcome = self._notification_engine.send_daily_morning_brief(
                    report,
                    pdf_result.output_path,
                    generation_seconds=elapsed,
                )
            elif report_type == "weekly":
                outcome = self._notification_engine.send_weekly_strategy_brief(
                    report,
                    pdf_result.output_path,
                    generation_seconds=elapsed,
                )
            else:
                outcome = self._notification_engine.send_monthly_report_brief(
                    report,
                    pdf_result.output_path,
                    generation_seconds=elapsed,
                )
            notification_payload = outcome.to_dict()

        logger.info(
            "Channel report flow completed type=%s report_id=%s pdf=%s notified=%s duration=%.3fs",
            report_type,
            report.get("report_id"),
            pdf_result.output_path,
            bool(notification_payload and notification_payload.get("delivered")),
            elapsed,
        )
        return DailyReportFlowResult(
            report=report,
            pdf_path=pdf_result.output_path,
            notification=notification_payload,
            generation_seconds=elapsed,
        )


def build_daily_report_flow(session: Session) -> DailyReportFlow:
    """Build the production local daily report flow from configured services."""

    return DailyReportFlow(
        report_engine=ReportEngine(session),
        pdf_engine=PDFEngine(output_dir=settings.storage_paths["reports"]),
        notification_engine=NotificationEngine(),
    )


def run_daily_report_from_local_json(
    session: Session,
    *,
    source_path: Path | None = None,
    report_type: str = "daily",
    send_notification: bool = True,
) -> DailyReportFlowResult:
    """Load structured local JSON and run the channel Report -> PDF -> Notification flow."""

    default_paths = {
        "daily": settings.daily_report_source_path,
        "weekly": settings.weekly_report_source_path,
        "monthly": settings.monthly_report_source_path,
    }
    provider = LocalJSONSourceProvider(source_path or default_paths[report_type])
    flow = build_daily_report_flow(session)
    return flow.run(provider.load_daily_sources(), report_type=report_type, send_notification=send_notification)
