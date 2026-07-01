"""Deterministic local keyword index generation."""

from __future__ import annotations

import re
from typing import Any

from .contracts import MemoryInput


class MemoryIndexer:
    """Extract bounded normalized terms without embeddings or external services."""

    _STOP_WORDS = {
        "and", "are", "for", "from", "into", "that", "the", "this", "with", "your",
        "was", "were", "has", "have", "had", "but", "not", "you",
    }

    def build_terms(self, value: MemoryInput) -> list[dict[str, str]]:
        typed: list[tuple[str, str | None]] = [
            ("topic", value.topic), ("game", value.game), ("category", value.category),
            ("video", value.video_id), ("type", value.memory_type),
        ]
        typed.extend(("keyword", item) for item in value.keywords)
        typed.extend(("tag", item) for item in value.tags)
        text = " ".join(
            part for part in (value.title, value.summary, self._flatten(value.content)) if part
        )
        typed.extend(("text", token) for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_+-]{2,}", text))
        terms: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for term_type, term in typed:
            normalized = self.normalize(term)
            key = (term_type, normalized)
            if not normalized or normalized in self._STOP_WORDS or key in seen:
                continue
            seen.add(key)
            terms.append({"term": str(term).strip()[:255], "normalized_term": normalized[:255], "term_type": term_type})
            if len(terms) >= 250:
                break
        return terms

    def normalize(self, value: str | None) -> str:
        return re.sub(r"\s+", " ", (value or "").strip().lower())

    def _flatten(self, value: Any) -> str:
        if isinstance(value, dict):
            return " ".join(f"{key} {self._flatten(item)}" for key, item in value.items())
        if isinstance(value, list):
            return " ".join(self._flatten(item) for item in value)
        return str(value) if isinstance(value, (str, int, float)) else ""
