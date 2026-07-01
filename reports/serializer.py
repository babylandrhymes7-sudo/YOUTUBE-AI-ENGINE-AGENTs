"""JSON-safe serialization for canonical report persistence."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


class ReportSerializer:
    """Serialize report ORM rows and arbitrary local structured values."""

    def report(self, row: Any, *, include_document: bool = True) -> dict[str, Any]:
        result = {
            "report_id": str(row.id),
            "logical_id": str(row.logical_id),
            "version": row.version,
            "previous_version_id": str(row.previous_version_id) if row.previous_version_id else None,
            "report_type": row.report_type,
            "title": row.title,
            "generated_at": row.generated_at.isoformat(),
            "period_start": row.period_start.isoformat() if row.period_start else None,
            "period_end": row.period_end.isoformat() if row.period_end else None,
            "channel_id": row.channel_id,
            "video_id": row.video_id,
            "game": row.game,
            "topic": row.topic,
            "category": row.category,
            "scores": self.json_safe(row.scores_json),
            "warnings": self.json_safe(row.warnings_json),
            "metadata": self.json_safe(row.metadata_json),
            "size_bytes": row.size_bytes,
            "is_archived": row.is_archived,
        }
        if include_document:
            result["document"] = self.json_safe(row.canonical_json)
        return result

    def json_safe(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, dict):
            return {str(key): self.json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.json_safe(item) for item in value]
        raise TypeError(f"report contains non-JSON value: {type(value).__name__}")
