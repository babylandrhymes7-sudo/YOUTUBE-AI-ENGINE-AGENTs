"""Post-process model recommendations into a deterministic execution order."""

from __future__ import annotations

from typing import Any

from .contracts import IntelligenceResult


class RecommendationEngine:
    """Normalize priority, ownership, evidence, and action ordering."""

    _PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    def prioritize(self, result: IntelligenceResult) -> IntelligenceResult:
        result.action_plan = [self._normalize(item, index) for index, item in enumerate(result.action_plan)]
        result.action_plan.sort(key=lambda item: (self._PRIORITY_ORDER[item["priority"]], item["rank"]))
        for rank, item in enumerate(result.action_plan, start=1):
            item["rank"] = rank
        return result

    def _normalize(self, item: dict[str, Any], index: int) -> dict[str, Any]:
        normalized = dict(item)
        priority = str(normalized.get("priority", "medium")).lower()
        normalized["priority"] = priority if priority in self._PRIORITY_ORDER else "medium"
        normalized["rank"] = index + 1
        normalized.setdefault("evidence", [])
        normalized.setdefault("expected_outcome", "")
        return normalized
