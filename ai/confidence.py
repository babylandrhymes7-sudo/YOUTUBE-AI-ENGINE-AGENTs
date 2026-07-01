"""Confidence normalization for AI intelligence sections."""

from __future__ import annotations

from .contracts import IntelligenceResult, KnowledgeContext


class ConfidenceScorer:
    """Combine model confidence with transparent input-coverage degradation."""

    _SECTIONS = ("analytics", "graph_intelligence", "competitor_intelligence", "news_intelligence")

    def score(self, result: IntelligenceResult, context: KnowledgeContext) -> IntelligenceResult:
        available = sum(bool(getattr(context, section)) for section in self._SECTIONS)
        coverage = available / len(self._SECTIONS)
        defaults = {
            "executive_summary": coverage,
            "key_findings": coverage,
            "action_plan": coverage,
            "video_ideas": coverage,
            "overall": coverage,
        }
        for key, default in defaults.items():
            supplied = result.confidence_scores.get(key, default)
            result.confidence_scores[key] = round(min(1.0, max(0.0, supplied)) * (0.5 + 0.5 * coverage), 4)
        if coverage < 0.5:
            result.degraded = True
            result.warnings.append("Confidence reduced because fewer than half of the primary knowledge sections were supplied.")
        return result
