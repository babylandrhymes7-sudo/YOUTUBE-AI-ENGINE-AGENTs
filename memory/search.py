"""Structured indexed search facade."""

from __future__ import annotations

from typing import Any

from .contracts import MemorySearchQuery
from .indexer import MemoryIndexer
from .repository import MemoryRepository
from .serializer import MemorySerializer
from .validator import MemoryValidator


class MemorySearch:
    """Validate, execute, and serialize paginated memory searches."""

    def __init__(
        self,
        repository: MemoryRepository,
        indexer: MemoryIndexer,
        validator: MemoryValidator,
        serializer: MemorySerializer,
    ) -> None:
        self._repository = repository
        self._indexer = indexer
        self._validator = validator
        self._serializer = serializer

    def search(self, query: MemorySearchQuery) -> dict[str, Any]:
        query = self._validator.validate_search(query)
        normalized = self._indexer.normalize(query.keyword) if query.keyword else None
        entries, total = self._repository.search(query, normalized)
        return {
            "items": [self._serializer.entry(entry) for entry in entries],
            "pagination": {
                "page": query.page,
                "page_size": query.page_size,
                "total": total,
                "pages": (total + query.page_size - 1) // query.page_size,
            },
            "query": {
                key: self._serializer.json_safe(value)
                for key, value in query.__dict__.items()
                if value is not None
            },
        }
