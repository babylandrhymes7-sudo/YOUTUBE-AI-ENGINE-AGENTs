"""PostgreSQL persistence and indexed history queries for canonical reports."""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from .contracts import ReportSearchQuery


class ReportRepository:
    """Persist immutable report versions and lazily load large sections."""

    def __init__(self, session: Session) -> None:
        self.session = session
        from database.models.report_engine import IntelligenceReport, IntelligenceReportSection

        self.Report = IntelligenceReport
        self.Section = IntelligenceReportSection

    def create_report(self, **data: Any) -> Any:
        row = self.Report(**data)
        self.session.add(row)
        self.session.flush()
        return row

    def create_sections(self, report_id: Any, sections: dict[str, dict[str, Any]], created_at: Any) -> None:
        self.session.add_all(
            [
                self.Section(
                    report_id=report_id,
                    section_key=key,
                    available=value["status"] == "available",
                    importance=value["importance"],
                    payload_json=value["data"],
                    warnings_json=value["warnings"],
                    created_at=created_at,
                )
                for key, value in sections.items()
            ]
        )
        self.session.flush()

    def get_report(self, report_id: Any) -> Any | None:
        return self.session.get(self.Report, report_id)

    def get_sections(self, report_id: Any, section_keys: list[str] | None = None) -> list[Any]:
        statement = select(self.Section).where(self.Section.report_id == report_id)
        if section_keys:
            statement = statement.where(self.Section.section_key.in_(section_keys))
        return list(self.session.scalars(statement.order_by(self.Section.importance.desc())))

    def latest_version(self, logical_id: Any) -> Any | None:
        statement = (
            select(self.Report)
            .where(self.Report.logical_id == logical_id)
            .order_by(self.Report.version.desc())
            .limit(1)
        )
        return self.session.scalars(statement).first()

    def search(self, query: ReportSearchQuery) -> tuple[list[Any], int]:
        Report = self.Report
        statement = select(Report)
        if query.latest_versions_only:
            latest = (
                select(
                    Report.logical_id.label("logical_id"),
                    func.max(Report.version).label("latest_version"),
                )
                .group_by(Report.logical_id)
                .subquery()
            )
            statement = statement.join(
                latest,
                and_(
                    Report.logical_id == latest.c.logical_id,
                    Report.version == latest.c.latest_version,
                ),
            )
        filters = []
        if query.date_from:
            filters.append(Report.generated_at >= query.date_from)
        if query.date_to:
            filters.append(Report.generated_at <= query.date_to)
        for column, value in (
            (Report.calendar_year, query.year),
            (Report.calendar_week, query.week),
            (Report.calendar_month, query.month),
            (Report.video_id, query.video_id),
            (Report.game, query.game),
            (Report.topic, query.topic),
            (Report.category, query.category),
            (Report.report_type, query.report_type),
        ):
            if value is not None:
                filters.append(
                    func.lower(column) == value.lower()
                    if isinstance(value, str)
                    else column == value
                )
        if not query.include_archived:
            filters.append(Report.is_archived.is_(False))
        if filters:
            statement = statement.where(*filters)
        total = int(
            self.session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
            or 0
        )
        statement = (
            statement.order_by(Report.generated_at.desc(), Report.id)
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        return list(self.session.scalars(statement)), total

    def latest(self, report_type: str | None = None) -> Any | None:
        statement = select(self.Report).where(self.Report.is_archived.is_(False))
        if report_type:
            statement = statement.where(self.Report.report_type == report_type)
        return self.session.scalars(statement.order_by(self.Report.generated_at.desc()).limit(1)).first()

    def history(self, logical_id: Any, *, offset: int = 0, limit: int = 100) -> list[Any]:
        statement = (
            select(self.Report)
            .where(self.Report.logical_id == logical_id)
            .order_by(self.Report.version.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))
