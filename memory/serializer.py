"""JSON-safe serialization for memory records and relationships."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


class MemorySerializer:
    """Serialize ORM entities without leaking SQLAlchemy implementation details."""

    def entry(self, value: Any) -> dict[str, Any]:
        return {
            "id": str(value.id),
            "logical_id": str(value.logical_id),
            "version": value.version,
            "previous_version_id": str(value.previous_version_id) if value.previous_version_id else None,
            "memory_type": value.memory_type,
            "category": value.category,
            "title": value.title,
            "summary": value.summary,
            "content": self.json_safe(value.content),
            "channel_id": value.channel_id,
            "video_id": value.video_id,
            "topic": value.topic,
            "game": value.game,
            "status": value.status,
            "confidence": float(value.confidence) if value.confidence is not None else None,
            "source_type": value.source_type,
            "source_id": value.source_id,
            "tags": value.tags or [],
            "keywords": value.keywords or [],
            "metadata": self.json_safe(value.metadata_json or {}),
            "created_at": value.created_at.isoformat(),
            "archived_at": value.archived_at.isoformat() if value.archived_at else None,
            "is_deleted": value.is_deleted,
        }

    def relationship(self, value: Any, related_entry: Any | None = None) -> dict[str, Any]:
        result = {
            "id": str(value.id),
            "source_entry_id": str(value.source_entry_id),
            "target_entry_id": str(value.target_entry_id),
            "relationship_type": value.relationship_type,
            "metadata": self.json_safe(value.metadata_json or {}),
            "created_at": value.created_at.isoformat(),
        }
        if related_entry is not None:
            result["entry"] = self.entry(related_entry)
        return result

    def json_safe(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, dict):
            return {str(key): self.json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.json_safe(item) for item in value]
        raise TypeError(f"memory contains non-JSON value: {type(value).__name__}")
