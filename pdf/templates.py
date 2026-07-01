"""Template context resolution for PDF rendering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class PDFTemplateContext:
    """Metadata and labels shared across all PDF pages."""

    report_type: str
    title: str
    generated_at: datetime
    author: str
    report_version: str
    generator: str
    application_version: str
    model_version: str


def resolve_context(report_json: dict[str, Any], *, app_version: str, model_version: str) -> PDFTemplateContext:
    """Build rendering context from structured report payload."""

    metadata = report_json.get("metadata", {}) if isinstance(report_json.get("metadata"), dict) else {}
    report_type = str(report_json.get("report_type", "executive")).lower()
    title = str(report_json.get("title") or metadata.get("title") or f"{report_type.title()} Intelligence Report")
    generated_raw = report_json.get("generated_at") or metadata.get("generated_at")
    generated_at = _parse_datetime(generated_raw)
    return PDFTemplateContext(
        report_type=report_type,
        title=title,
        generated_at=generated_at,
        author=str(metadata.get("author") or "YOUTUBE AI AGENT"),
        report_version=str(report_json.get("version") or metadata.get("version") or "1"),
        generator=str(metadata.get("generator") or "YOUTUBE AI AGENT PDF Engine"),
        application_version=app_version,
        model_version=model_version,
    )


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)
