"""Stable transport contracts for the AI Intelligence Engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class KnowledgeContext:
    """Structured knowledge supplied by the Knowledge Engine."""

    analytics: dict[str, Any] = field(default_factory=dict)
    graph_intelligence: dict[str, Any] = field(default_factory=dict)
    competitor_intelligence: dict[str, Any] = field(default_factory=dict)
    news_intelligence: dict[str, Any] = field(default_factory=dict)
    predictions: dict[str, Any] = field(default_factory=dict)
    historical_memory: dict[str, Any] = field(default_factory=dict)
    experiment_results: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "KnowledgeContext":
        """Validate the top-level knowledge contract without querying any source."""

        if not isinstance(value, dict):
            raise TypeError("knowledge context must be a JSON object")
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unsupported knowledge sections: {sorted(unknown)}")
        for key, section in value.items():
            if not isinstance(section, dict):
                raise TypeError(f"knowledge section '{key}' must be a JSON object")
        return cls(**value)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IntelligenceResult:
    """Stable structured output returned to reports and downstream workflows."""

    executive_summary: str = ""
    channel_health: dict[str, Any] = field(default_factory=dict)
    key_findings: list[dict[str, Any]] = field(default_factory=list)
    growth_opportunities: list[dict[str, Any]] = field(default_factory=list)
    threats: list[dict[str, Any]] = field(default_factory=list)
    predictions: list[dict[str, Any]] = field(default_factory=list)
    action_plan: list[dict[str, Any]] = field(default_factory=list)
    video_ideas: list[dict[str, Any]] = field(default_factory=list)
    thumbnail_ideas: list[dict[str, Any]] = field(default_factory=list)
    seo_suggestions: list[dict[str, Any]] = field(default_factory=list)
    confidence_scores: dict[str, float] = field(default_factory=dict)
    raw_ai_response: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    degraded: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
