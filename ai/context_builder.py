"""Build bounded model context exclusively from supplied structured knowledge."""

from __future__ import annotations

import json
from typing import Any

from .contracts import KnowledgeContext


class ContextBuilder:
    """Serialize structured knowledge deterministically without external lookups."""

    def __init__(self, max_characters: int = 200_000) -> None:
        self._max_characters = max_characters

    def build(self, context: KnowledgeContext) -> str:
        value = self._json_safe(context.to_dict())
        rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        if len(rendered) > self._max_characters:
            raise ValueError(
                f"knowledge context exceeds configured limit ({len(rendered)} > {self._max_characters})"
            )
        return rendered

    def _json_safe(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_safe(item) for item in value]
        if hasattr(value, "isoformat"):
            return value.isoformat()
        raise TypeError(f"knowledge context contains a non-JSON value: {type(value).__name__}")
