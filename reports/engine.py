"""Canonical Report Engine orchestration."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.logging import get_logger

from .assembler import ReportAssembler
from .contracts import ReportRequest, ReportSearchQuery
from .repository import ReportRepository
from .scoring import ReportScorer
from .serializer import ReportSerializer
from .validator import ReportValidationError, ReportValidator

logger = get_logger(__name__)


class ReportNotFoundError(LookupError):
    """Raised when a canonical report cannot be found."""


class DuplicateReportError(ValueError):
    """Raised when an identical report version is persisted concurrently."""


class ReportEngine:
    """Validate supplied subsystem JSON and compose immutable canonical reports."""

    def __init__(
        self,
        session: Session,
        *,
        repository: ReportRepository | None = None,
        validator: ReportValidator | None = None,
        assembler: ReportAssembler | None = None,
        scorer: ReportScorer | None = None,
        serializer: ReportSerializer | None = None,
    ) -> None:
        self._session = session
        self._repository = repository or ReportRepository(session)
        self._validator = validator or ReportValidator()
        self._assembler = assembler or ReportAssembler()
        self._scorer = scorer or ReportScorer()
        self._serializer = serializer or ReportSerializer()

    def generate_daily_report(self, sources: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self.generate_report(ReportRequest(report_type="daily", sources=sources, **kwargs))

    def generate_weekly_report(self, sources: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self.generate_report(ReportRequest(report_type="weekly", sources=sources, **kwargs))

    def generate_monthly_report(self, sources: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self.generate_report(ReportRequest(report_type="monthly", sources=sources, **kwargs))

    def generate_custom_report(self, sources: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self.generate_report(ReportRequest(report_type="custom", sources=sources, **kwargs))

    def generate_historical_report(self, sources: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self.generate_report(ReportRequest(report_type="historical", sources=sources, **kwargs))

    def generate_comparison_report(self, sources: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self.generate_report(ReportRequest(report_type="comparison", sources=sources, **kwargs))

    def generate_report(
        self,
        request: ReportRequest,
        *,
        logical_id: Any | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        """Build, validate, and persist one canonical report version."""

        started = perf_counter()
        try:
            request = self._validator.validate_request(request)
        except ReportValidationError:
            logger.exception("Report request validation failed type=%s", request.report_type)
            raise
        sources, validation_warnings = self._validator.validate_sources(request.sources)
        scores = self._scorer.score(sources)
        sections, warnings = self._assembler.assemble(sources, scores, validation_warnings)

        generated_at = request.generated_at or datetime.now(timezone.utc)
        report_id = uuid.uuid4()
        resolved_logical_id = uuid.UUID(str(logical_id)) if logical_id else uuid.uuid4()
        previous = self._repository.latest_version(resolved_logical_id) if logical_id else None
        if logical_id and previous is None:
            raise ReportNotFoundError(f"logical report not found: {logical_id}")
        version = previous.version + 1 if previous else 1
        metadata = {
            **self._serializer.json_safe(request.metadata),
            "schema_version": "1.0",
            "input_sources": sorted(sources),
            "section_importance": {
                key: section["importance"] for key, section in sections.items()
            },
        }
        document: dict[str, Any] = {
            "report_id": str(report_id),
            "logical_id": str(resolved_logical_id),
            "version": version,
            "report_type": request.report_type,
            "generated_at": generated_at.isoformat(),
            "period_start": request.period_start.isoformat() if request.period_start else None,
            "period_end": request.period_end.isoformat() if request.period_end else None,
            "scores": scores,
            "warnings": warnings,
            "metadata": metadata,
        }
        document.update(
            {
                key: {
                    "status": section["status"],
                    "data": section["data"],
                    "warnings": section["warnings"],
                }
                for key, section in sections.items()
            }
        )
        return self.save_report(
            request,
            document,
            sections,
            scores,
            warnings,
            report_id=report_id,
            logical_id=resolved_logical_id,
            version=version,
            previous_version_id=previous.id if previous else None,
            generated_at=generated_at,
            started_at=started,
            commit=commit,
        )

    def save_report(
        self,
        request: ReportRequest,
        document: dict[str, Any],
        sections: dict[str, dict[str, Any]],
        scores: dict[str, float | None],
        warnings: list[str],
        *,
        report_id: Any,
        logical_id: Any,
        version: int,
        previous_version_id: Any | None,
        generated_at: datetime,
        started_at: float | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        """Persist an already assembled canonical JSON report without rendering it."""

        safe_document = self._serializer.json_safe(document)
        encoded = json.dumps(safe_document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        content_hash = hashlib.sha256(encoded).hexdigest()
        iso_calendar = generated_at.isocalendar()
        try:
            row = self._repository.create_report(
                id=report_id,
                logical_id=logical_id,
                version=version,
                previous_version_id=previous_version_id,
                report_type=request.report_type,
                title=request.title or self._default_title(request.report_type, generated_at),
                generated_at=generated_at,
                period_start=request.period_start,
                period_end=request.period_end,
                calendar_year=iso_calendar[0],
                calendar_week=iso_calendar[1],
                calendar_month=generated_at.month,
                channel_id=self._clean(request.channel_id),
                video_id=self._clean(request.video_id),
                game=self._clean(request.game),
                topic=self._clean(request.topic),
                category=self._clean(request.category),
                canonical_json=safe_document,
                scores_json=scores,
                warnings_json=warnings,
                metadata_json=safe_document["metadata"],
                content_hash=content_hash,
                size_bytes=len(encoded),
                is_archived=False,
            )
            self._repository.create_sections(row.id, sections, generated_at)
            if commit:
                self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            logger.exception("Report persistence constraint failed type=%s version=%s", request.report_type, version)
            raise DuplicateReportError("an identical report version already exists") from exc
        except Exception:
            self._session.rollback()
            logger.exception("Report persistence failed type=%s version=%s", request.report_type, version)
            raise
        duration_ms = ((perf_counter() - started_at) * 1000.0) if started_at is not None else 0.0
        for warning in warnings:
            logger.warning("Report warning report_id=%s warning=%s", row.id, warning)
        logger.info(
            "Report created id=%s type=%s version=%s duration_ms=%.2f size_bytes=%s warnings=%s",
            row.id,
            row.report_type,
            row.version,
            duration_ms,
            row.size_bytes,
            len(warnings),
        )
        return self._serializer.report(row)

    def load_report(
        self,
        report_id: Any,
        *,
        include_document: bool = True,
        section_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        row = self._repository.get_report(report_id)
        if row is None:
            raise ReportNotFoundError(f"report not found: {report_id}")
        result = self._serializer.report(row, include_document=include_document)
        if section_keys is not None:
            result["sections"] = {
                section.section_key: {
                    "status": "available" if section.available else "unavailable",
                    "data": self._serializer.json_safe(section.payload_json),
                    "warnings": section.warnings_json,
                }
                for section in self._repository.get_sections(report_id, section_keys)
            }
        return result

    def search_reports(self, query: ReportSearchQuery | dict[str, Any]) -> dict[str, Any]:
        resolved = query if isinstance(query, ReportSearchQuery) else ReportSearchQuery(**query)
        resolved = self._validator.validate_search(resolved)
        rows, total = self._repository.search(resolved)
        logger.info(
            "Report search page=%s page_size=%s total=%s", resolved.page, resolved.page_size, total
        )
        return {
            "items": [self._serializer.report(row, include_document=False) for row in rows],
            "pagination": {
                "page": resolved.page,
                "page_size": resolved.page_size,
                "total": total,
                "pages": (total + resolved.page_size - 1) // resolved.page_size,
            },
        }

    def get_latest_report(self, report_type: str | None = None) -> dict[str, Any] | None:
        if report_type:
            self._validator.validate_search(ReportSearchQuery(report_type=report_type))
        row = self._repository.latest(report_type)
        return self._serializer.report(row) if row else None

    def get_report_history(self, logical_id: Any, *, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        self._validator.validate_search(ReportSearchQuery(page=page, page_size=page_size))
        rows = self._repository.history(
            logical_id, offset=(page - 1) * page_size, limit=page_size
        )
        return {
            "logical_id": str(logical_id),
            "items": [self._serializer.report(row, include_document=False) for row in rows],
        }

    def compare_reports(self, left_report_id: Any, right_report_id: Any) -> dict[str, Any]:
        left = self._repository.get_report(left_report_id)
        right = self._repository.get_report(right_report_id)
        if left is None or right is None:
            missing = left_report_id if left is None else right_report_id
            raise ReportNotFoundError(f"report not found: {missing}")
        score_keys = sorted(set(left.scores_json) | set(right.scores_json))
        score_comparison = {}
        for key in score_keys:
            left_value, right_value = left.scores_json.get(key), right.scores_json.get(key)
            score_comparison[key] = {
                "left": left_value,
                "right": right_value,
                "change": (
                    round(right_value - left_value, 2)
                    if left_value is not None and right_value is not None
                    else None
                ),
            }
        section_keys = self._assembler.SECTION_SPECS
        availability_changes = [
            key
            for key in section_keys
            if left.canonical_json.get(key, {}).get("status")
            != right.canonical_json.get(key, {}).get("status")
        ]
        return {
            "left_report_id": str(left.id),
            "right_report_id": str(right.id),
            "score_comparison": score_comparison,
            "section_availability_changes": availability_changes,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _default_title(self, report_type: str, generated_at: datetime) -> str:
        return f"{report_type.title()} Intelligence Report — {generated_at.date().isoformat()}"

    def _clean(self, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None
