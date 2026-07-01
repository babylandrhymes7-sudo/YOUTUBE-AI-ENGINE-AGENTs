"""Input and query contracts for the Memory Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MemoryInput:
    """One proposed immutable memory version."""

    memory_type: str
    content: dict[str, Any]
    category: str | None = None
    title: str | None = None
    summary: str | None = None
    channel_id: str | None = None
    video_id: str | None = None
    topic: str | None = None
    game: str | None = None
    status: str = "active"
    confidence: float | None = None
    source_type: str | None = None
    source_id: str | None = None
    tags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MemoryInput":
        if not isinstance(value, dict):
            raise TypeError("memory input must be an object")
        value = dict(value)
        if "related_video" in value and "video_id" not in value:
            value["video_id"] = value.pop("related_video")
        content_fields = ("outcome", "related_reports", "related_predictions", "actual_result")
        extracted_content = {
            key: value.pop(key) for key in content_fields if key in value
        }
        if "content" not in value and extracted_content:
            value["content"] = extracted_content
        elif extracted_content:
            if not isinstance(value["content"], dict):
                raise TypeError("content must be an object")
            value["content"] = {**value["content"], **extracted_content}
        if isinstance(value.get("created_at"), str):
            value["created_at"] = datetime.fromisoformat(value["created_at"].replace("Z", "+00:00"))
        allowed = set(cls.__dataclass_fields__)
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unsupported memory fields: {sorted(unknown)}")
        return cls(**value)


@dataclass(frozen=True)
class RelationshipInput:
    """A typed relationship from the saved memory to another entry."""

    target_entry_id: Any
    relationship_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemorySearchQuery:
    """Indexed memory search filters and pagination."""

    date_from: datetime | None = None
    date_to: datetime | None = None
    video_id: str | None = None
    topic: str | None = None
    game: str | None = None
    keyword: str | None = None
    recommendation: str | None = None
    prediction: str | None = None
    memory_type: str | None = None
    competitor: str | None = None
    report: str | None = None
    category: str | None = None
    status: str | None = None
    include_archived: bool = False
    include_deleted: bool = False
    latest_versions_only: bool = True
    page: int = 1
    page_size: int = 50
