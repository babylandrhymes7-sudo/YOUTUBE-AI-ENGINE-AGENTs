"""Canonical section assembly, deduplication, and priority ordering."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SectionSpec:
    paths: tuple[str, ...]
    importance: int


class ReportAssembler:
    """Merge validated source JSON into one stable, extensible report schema."""

    SECTION_SPECS: dict[str, SectionSpec] = {
        "executive_summary": SectionSpec(("ai_intelligence.executive_summary", "knowledge.executive_summary"), 100),
        "channel_health_score": SectionSpec(("scores.channel_health_score",), 98),
        "overall_performance": SectionSpec(("analytics.overall_performance", "knowledge.overall_performance"), 96),
        "latest_upload_analysis": SectionSpec(("analytics.latest_upload_analysis",), 94),
        "channel_analytics_summary": SectionSpec(("analytics.summary", "analytics.channel_summary"), 92),
        "graph_intelligence_summary": SectionSpec(("graph_intelligence.summary", "graph_intelligence"), 90),
        "retention_analysis": SectionSpec(("graph_intelligence.retention_analysis", "analytics.retention_analysis"), 89),
        "ctr_analysis": SectionSpec(("graph_intelligence.ctr_analysis", "analytics.ctr_analysis"), 88),
        "subscriber_growth": SectionSpec(("analytics.subscriber_growth",), 86),
        "watch_time_analysis": SectionSpec(("analytics.watch_time_analysis",), 84),
        "traffic_sources": SectionSpec(("analytics.traffic_sources", "graph_intelligence.traffic_sources"), 82),
        "audience_analysis": SectionSpec(("analytics.audience_analysis", "knowledge.audience_analysis"), 80),
        "competitor_analysis": SectionSpec(("competitors.analysis", "competitor_intelligence.analysis", "competitors"), 78),
        "news_summary": SectionSpec(("news.summary", "news_intelligence.summary", "news"), 76),
        "trending_topics": SectionSpec(("news.trending_topics", "knowledge.trending_topics"), 74),
        "prediction_summary": SectionSpec(("predictions.summary", "predictions"), 72),
        "recommendation_summary": SectionSpec(("ai_intelligence.recommendations", "memory.recommendations", "knowledge.recommendations"), 70),
        "video_ideas": SectionSpec(("ai_intelligence.video_ideas", "knowledge.video_ideas"), 68),
        "thumbnail_ideas": SectionSpec(("ai_intelligence.thumbnail_ideas", "knowledge.thumbnail_ideas"), 66),
        "title_suggestions": SectionSpec(("ai_intelligence.title_suggestions", "knowledge.title_suggestions"), 64),
        "seo_suggestions": SectionSpec(("ai_intelligence.seo_suggestions", "knowledge.seo_suggestions"), 62),
        "action_plan": SectionSpec(("ai_intelligence.action_plan", "knowledge.action_plan"), 95),
        "warnings": SectionSpec(("ai_intelligence.warnings", "knowledge.warnings"), 93),
        "opportunities": SectionSpec(("ai_intelligence.growth_opportunities", "knowledge.opportunities"), 91),
        "confidence_scores": SectionSpec(("scores", "ai_intelligence.confidence_scores"), 87),
        "appendix": SectionSpec(("knowledge.appendix",), 10),
    }

    def assemble(
        self,
        sources: dict[str, dict[str, Any]],
        scores: dict[str, float | None],
        validation_warnings: list[str],
    ) -> tuple[dict[str, dict[str, Any]], list[str]]:
        enriched = {**sources, "scores": scores}
        sections: dict[str, dict[str, Any]] = {}
        warnings = list(validation_warnings)
        for key, spec in self.SECTION_SPECS.items():
            value = self._first(enriched, spec.paths)
            if value is None or value == {} or value == [] or value == "":
                message = f"Section '{key}' is unavailable."
                warnings.append(message)
                sections[key] = {
                    "status": "unavailable",
                    "data": None,
                    "warnings": [message],
                    "importance": spec.importance,
                }
                continue
            sections[key] = {
                "status": "available",
                "data": self._normalize(value),
                "warnings": [],
                "importance": spec.importance,
            }
        known_sources = {
            "knowledge", "analytics", "predictions", "memory", "competitors",
            "competitor_intelligence", "news", "news_intelligence",
            "graph_intelligence", "ai_intelligence",
        }
        extensions = {name: value for name, value in sources.items() if name not in known_sources}
        if extensions:
            appendix = sections["appendix"]
            existing = appendix["data"] if isinstance(appendix["data"], dict) else {}
            appendix.update(
                status="available",
                data={**existing, "extension_sources": extensions},
                warnings=[],
            )
        return sections, self._deduplicate_strings(warnings)

    def _first(self, root: dict[str, Any], paths: tuple[str, ...]) -> Any:
        for path in paths:
            current: Any = root
            for segment in path.split("."):
                if not isinstance(current, dict) or segment not in current:
                    current = None
                    break
                current = current[segment]
            if current is not None:
                return current
        return None

    def _normalize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            normalized = [self._normalize(item) for item in value]
            deduplicated: list[Any] = []
            seen: set[str] = set()
            for item in normalized:
                marker = json.dumps(item, sort_keys=True, separators=(",", ":"), default=str)
                if marker not in seen:
                    seen.add(marker)
                    deduplicated.append(item)
            if deduplicated and all(isinstance(item, dict) for item in deduplicated):
                if any(any(key in item for key in ("priority", "severity", "importance")) for item in deduplicated):
                    deduplicated.sort(key=self._priority_key)
            return deduplicated
        return value

    def _priority_key(self, item: dict[str, Any]) -> tuple[int, float]:
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        priority = order.get(str(item.get("priority", item.get("severity", "medium"))).lower(), 2)
        try:
            importance = -float(item.get("importance", 0))
        except (TypeError, ValueError):
            importance = 0.0
        return priority, importance

    def _deduplicate_strings(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))
