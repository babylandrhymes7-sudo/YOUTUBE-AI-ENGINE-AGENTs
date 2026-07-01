"""Configurable composition of precomputed subsystem scores."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScoreRule:
    paths: tuple[str, ...]
    weight: float = 1.0
    input_scale: float = 100.0


@dataclass(frozen=True)
class ReportScoringConfig:
    """Paths are replaceable without changing report assembly logic."""

    rules: dict[str, ScoreRule] = field(default_factory=lambda: {
        "channel_health_score": ScoreRule(("analytics.scores.channel_health", "knowledge.scores.channel_health")),
        "growth_score": ScoreRule(("analytics.scores.growth", "knowledge.scores.growth")),
        "consistency_score": ScoreRule(("analytics.scores.consistency",)),
        "packaging_score": ScoreRule(("analytics.scores.packaging", "knowledge.scores.packaging")),
        "content_quality_score": ScoreRule(("analytics.scores.content_quality",)),
        "audience_health_score": ScoreRule(("analytics.scores.audience_health",)),
        "prediction_confidence": ScoreRule(("predictions.confidence", "predictions.scores.confidence"), input_scale=1.0),
        "overall_ai_confidence": ScoreRule(("ai_intelligence.confidence_scores.overall",), input_scale=1.0),
    })


class ReportScorer:
    """Consume supplied scores; never derive scores from raw performance metrics."""

    def __init__(self, config: ReportScoringConfig | None = None) -> None:
        self._config = config or ReportScoringConfig()

    def score(self, sources: dict[str, dict[str, Any]]) -> dict[str, float | None]:
        result: dict[str, float | None] = {}
        weighted: list[tuple[float, float]] = []
        for name, rule in self._config.rules.items():
            raw = None
            for path in rule.paths:
                candidate = self._read_path(sources, path)
                if candidate is not None:
                    raw = candidate
                    break
            value = self._normalize(raw, rule.input_scale)
            result[name] = value
            if value is not None and name not in {"prediction_confidence", "overall_ai_confidence"}:
                weighted.append((value, rule.weight))
        result["overall_performance_score"] = (
            round(sum(value * weight for value, weight in weighted) / sum(weight for _, weight in weighted), 2)
            if weighted
            else None
        )
        return result

    def _read_path(self, sources: dict[str, dict[str, Any]], path: str) -> Any:
        current: Any = sources
        for segment in path.split("."):
            if not isinstance(current, dict) or segment not in current:
                return None
            current = current[segment]
        return current

    def _normalize(self, value: Any, scale: float) -> float | None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if scale == 1.0:
            numeric *= 100.0
        return round(min(100.0, max(0.0, numeric)), 2)
