"""Defensive recovery and validation for model-generated intelligence JSON."""

from __future__ import annotations

import json
import re
from typing import Any

from .contracts import IntelligenceResult


class ResponseParser:
    """Convert imperfect local-model output into the stable result contract."""

    _LIST_FIELDS = (
        "key_findings",
        "growth_opportunities",
        "threats",
        "predictions",
        "action_plan",
        "video_ideas",
        "thumbnail_ideas",
        "seo_suggestions",
    )

    def parse(self, raw: str) -> IntelligenceResult:
        warnings: list[str] = []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            candidate = self._extract_json(raw)
            if candidate is None:
                return IntelligenceResult(
                    executive_summary=raw.strip(),
                    raw_ai_response=raw,
                    degraded=True,
                    warnings=["Model response was not valid JSON."],
                )
            try:
                payload = json.loads(candidate)
                warnings.append("Recovered JSON from surrounding model text.")
            except json.JSONDecodeError:
                repaired = self._repair(candidate)
                try:
                    payload = json.loads(repaired)
                    warnings.append("Recovered malformed JSON with conservative repairs.")
                except json.JSONDecodeError:
                    return IntelligenceResult(
                        executive_summary=raw.strip(),
                        raw_ai_response=raw,
                        degraded=True,
                        warnings=["Model response JSON could not be recovered."],
                    )
        if not isinstance(payload, dict):
            return IntelligenceResult(
                executive_summary=str(payload),
                raw_ai_response=raw,
                degraded=True,
                warnings=["Model response root was not a JSON object."],
            )
        normalized = self._normalize_keys(payload)
        result = IntelligenceResult(
            executive_summary=str(normalized.get("executive_summary", "")),
            channel_health=self._dict(normalized.get("channel_health")),
            confidence_scores=self._scores(normalized.get("confidence_scores")),
            raw_ai_response=raw,
            warnings=warnings,
        )
        for field_name in self._LIST_FIELDS:
            setattr(result, field_name, self._list_of_dicts(normalized.get(field_name)))
        return result

    def _extract_json(self, value: str) -> str | None:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", value, re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1)
        start = value.find("{")
        if start < 0:
            return None
        depth, quoted, escaped = 0, False, False
        for index in range(start, len(value)):
            character = value[index]
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == '"':
                quoted = not quoted
            elif not quoted:
                if character == "{":
                    depth += 1
                elif character == "}":
                    depth -= 1
                    if depth == 0:
                        return value[start : index + 1]
        return None

    def _repair(self, value: str) -> str:
        value = re.sub(r",\s*([}\]])", r"\1", value)
        return value.replace("\u201c", '"').replace("\u201d", '"')

    def _normalize_keys(self, value: dict[str, Any]) -> dict[str, Any]:
        return {re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_"): item for key, item in value.items()}

    def _dict(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _list_of_dicts(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item if isinstance(item, dict) else {"text": str(item)} for item in value]

    def _scores(self, value: Any) -> dict[str, float]:
        if not isinstance(value, dict):
            return {}
        result: dict[str, float] = {}
        for key, score in value.items():
            try:
                result[str(key)] = min(1.0, max(0.0, float(score)))
            except (TypeError, ValueError):
                continue
        return result
