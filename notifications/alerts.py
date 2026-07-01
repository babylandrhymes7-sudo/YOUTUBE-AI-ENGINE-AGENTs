"""Deterministic alert evaluation for incoming subsystem JSON."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .contracts import NotificationCategory, NotificationMessage, NotificationPriority


@dataclass(frozen=True)
class AlertDecision:
    should_notify: bool
    reason: str | None = None
    message: NotificationMessage | None = None


class AlertManager:
    def __init__(self, *, min_confidence: float = 0.85, min_impact: float = 0.65, min_delta_percent: float = 15.0) -> None:
        self.min_confidence = min_confidence
        self.min_impact = min_impact
        self.min_delta_percent = min_delta_percent

    def evaluate(self, event: dict[str, Any]) -> AlertDecision:
        if not isinstance(event, dict):
            return AlertDecision(False, "event must be a JSON object")
        event_type = str(event.get("event_type") or event.get("type") or "instant_ai_alert")
        confidence = self._as_float(event.get("confidence"))
        impact = self._as_float(event.get("impact"))
        delta_percent = self._as_float(event.get("delta_percent") or event.get("delta"))
        priority = str(event.get("priority") or "normal").lower()
        if confidence is None or confidence < self.min_confidence:
            return AlertDecision(False, "confidence below threshold")
        if impact is not None and impact < self.min_impact:
            return AlertDecision(False, "impact below threshold")
        if delta_percent is not None and abs(delta_percent) < self.min_delta_percent and event_type not in {
            "prediction_high_confidence",
            "major_news",
            "historical_repeat",
        }:
            return AlertDecision(False, "delta below threshold")
        if priority not in {"high", "urgent"} and confidence < 0.95:
            return AlertDecision(False, "priority filter blocked notification")
        message = self._build_message(event, event_type, confidence)
        return AlertDecision(True, message=message)

    def _build_message(self, event: dict[str, Any], event_type: str, confidence: float) -> NotificationMessage:
        happened = self._first_text(event, "what_happened", "description", "summary", "message") or event_type.replace("_", " ").title()
        why_it_matters = self._first_text(event, "why_it_matters", "significance", "impact_summary") or "This crosses the configured alert threshold."
        expected_impact = self._first_text(event, "expected_impact", "impact_summary") or "Likely to influence near-term performance."
        recommended_action = self._first_text(event, "recommended_action", "action") or "Review the opportunity and respond quickly."
        urgency = str(event.get("urgency") or event.get("priority") or "high").title()
        notification_id = self._notification_id(event_type, event)
        body = (
            f"What happened: {happened}\n\n"
            f"Why it matters: {why_it_matters}\n\n"
            f"Expected impact: {expected_impact}\n\n"
            f"Recommended action: {recommended_action}\n\n"
            f"Urgency: {urgency}\nConfidence: {round(confidence * 100)}%"
        )
        return NotificationMessage(
            notification_id=notification_id,
            category=NotificationCategory.INSTANT_AI_ALERT,
            title="Opportunity Detected",
            summary=happened,
            body=body,
            data=event,
            priority=NotificationPriority.URGENT if urgency.lower() == "urgent" else NotificationPriority.HIGH,
            confidence=confidence,
        )

    def _notification_id(self, event_type: str, event: dict[str, Any]) -> str:
        payload = json.dumps({"event_type": event_type, "event": event}, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _first_text(self, event: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _as_float(self, value: Any) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None
