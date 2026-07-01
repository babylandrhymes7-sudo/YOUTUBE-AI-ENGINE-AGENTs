"""Strict validation for immutable memory records and relationships."""

from __future__ import annotations

from datetime import timezone
from typing import Any

from .contracts import MemoryInput, MemorySearchQuery, RelationshipInput


class MemoryValidationError(ValueError):
    """Raised when malformed knowledge is rejected."""


class MemoryValidator:
    """Validate contracts without persistence or business side effects."""

    MEMORY_TYPES = {
        "daily_report", "weekly_report", "monthly_report", "recommendation", "prediction",
        "analytics_snapshot", "video_performance", "competitor_history", "news_summary",
        "graph_summary", "experiment", "user_note", "video_idea", "thumbnail_suggestion",
        "title_suggestion", "actual_result", "knowledge",
    }

    def validate_memory(self, value: MemoryInput) -> MemoryInput:
        if value.memory_type not in self.MEMORY_TYPES:
            raise MemoryValidationError(f"unsupported memory_type: {value.memory_type}")
        if not isinstance(value.content, dict) or not value.content:
            raise MemoryValidationError("content must be a non-empty object")
        if value.confidence is not None and not 0.0 <= value.confidence <= 1.0:
            raise MemoryValidationError("confidence must be between 0 and 1")
        for name in ("tags", "keywords"):
            items = getattr(value, name)
            if not isinstance(items, list) or any(not isinstance(item, str) or not item.strip() for item in items):
                raise MemoryValidationError(f"{name} must contain non-empty strings")
        if value.created_at is not None and value.created_at.tzinfo is None:
            raise MemoryValidationError("created_at must be timezone-aware")
        return value

    def validate_relationship(self, value: RelationshipInput, source_entry_id: Any) -> RelationshipInput:
        if not value.relationship_type.strip():
            raise MemoryValidationError("relationship_type is required")
        if str(value.target_entry_id) == str(source_entry_id):
            raise MemoryValidationError("memory entries cannot relate to themselves")
        if not isinstance(value.metadata, dict):
            raise MemoryValidationError("relationship metadata must be an object")
        return value

    def validate_search(self, query: MemorySearchQuery) -> MemorySearchQuery:
        if query.page < 1:
            raise MemoryValidationError("page must be at least 1")
        if query.page_size < 1 or query.page_size > 500:
            raise MemoryValidationError("page_size must be between 1 and 500")
        if query.date_from and query.date_from.tzinfo is None:
            raise MemoryValidationError("date_from must be timezone-aware")
        if query.date_to and query.date_to.tzinfo is None:
            raise MemoryValidationError("date_to must be timezone-aware")
        if query.date_from and query.date_to and query.date_from > query.date_to:
            raise MemoryValidationError("date_from cannot be after date_to")
        return query
