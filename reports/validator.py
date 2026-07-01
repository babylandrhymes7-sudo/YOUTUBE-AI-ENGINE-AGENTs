"""Resilient validation for report requests and subsystem sections."""

from __future__ import annotations

from typing import Any

from .contracts import REPORT_TYPES, ReportRequest, ReportSearchQuery


class ReportValidationError(ValueError):
    """Raised for invalid report metadata that prevents safe generation."""


class ReportValidator:
    """Validate report metadata strictly and source sections gracefully."""

    def validate_request(self, request: ReportRequest) -> ReportRequest:
        if request.report_type not in REPORT_TYPES:
            raise ReportValidationError(f"unsupported report_type: {request.report_type}")
        if not isinstance(request.sources, dict):
            raise ReportValidationError("sources must be an object")
        if not isinstance(request.metadata, dict):
            raise ReportValidationError("metadata must be an object")
        for name, value in (
            ("generated_at", request.generated_at),
            ("period_start", request.period_start),
            ("period_end", request.period_end),
        ):
            if value is not None and value.tzinfo is None:
                raise ReportValidationError(f"{name} must be timezone-aware")
        if request.period_start and request.period_end and request.period_start > request.period_end:
            raise ReportValidationError("period_start cannot be after period_end")
        return request

    def validate_sources(self, sources: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
        valid: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        for source_name, payload in sources.items():
            if not isinstance(source_name, str) or not source_name.strip():
                warnings.append("Ignored a source with an invalid name.")
                continue
            if not isinstance(payload, dict):
                warnings.append(f"Source '{source_name}' is malformed and was marked unavailable.")
                continue
            valid[source_name.strip().lower()] = payload
        return valid, warnings

    def validate_search(self, query: ReportSearchQuery) -> ReportSearchQuery:
        if query.report_type and query.report_type not in REPORT_TYPES:
            raise ReportValidationError(f"unsupported report_type: {query.report_type}")
        if query.page < 1 or not 1 <= query.page_size <= 500:
            raise ReportValidationError("page must be >= 1 and page_size must be between 1 and 500")
        if query.week is not None and not 1 <= query.week <= 53:
            raise ReportValidationError("week must be between 1 and 53")
        if query.month is not None and not 1 <= query.month <= 12:
            raise ReportValidationError("month must be between 1 and 12")
        if query.date_from and query.date_from.tzinfo is None:
            raise ReportValidationError("date_from must be timezone-aware")
        if query.date_to and query.date_to.tzinfo is None:
            raise ReportValidationError("date_to must be timezone-aware")
        if query.date_from and query.date_to and query.date_from > query.date_to:
            raise ReportValidationError("date_from cannot be after date_to")
        return query
