"""Append-only Memory Engine orchestration."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.logging import get_logger

from .contracts import MemoryInput, MemorySearchQuery, RelationshipInput
from .indexer import MemoryIndexer
from .repository import MemoryRepository
from .search import MemorySearch
from .serializer import MemorySerializer
from .validator import MemoryValidationError, MemoryValidator

logger = get_logger(__name__)


class DuplicateMemoryError(ValueError):
    """Raised when an identical immutable memory version already exists."""


class MemoryNotFoundError(LookupError):
    """Raised when a requested memory or relationship target does not exist."""


class MemoryEngine:
    """Store, version, search, and relate all local historical knowledge."""

    def __init__(
        self,
        session: Session,
        *,
        repository: MemoryRepository | None = None,
        indexer: MemoryIndexer | None = None,
        serializer: MemorySerializer | None = None,
        validator: MemoryValidator | None = None,
    ) -> None:
        self._session = session
        self._repository = repository or MemoryRepository(session)
        self._indexer = indexer or MemoryIndexer()
        self._serializer = serializer or MemorySerializer()
        self._validator = validator or MemoryValidator()
        self._search = MemorySearch(
            self._repository, self._indexer, self._validator, self._serializer
        )

    def save_memory(
        self,
        value: MemoryInput | dict[str, Any],
        *,
        logical_id: Any | None = None,
        relationships: Iterable[RelationshipInput] = (),
        commit: bool = True,
    ) -> dict[str, Any]:
        """Save a new memory or append the next version of an existing memory."""

        try:
            payload = value if isinstance(value, MemoryInput) else MemoryInput.from_dict(value)
            payload = self._validator.validate_memory(payload)
        except (TypeError, ValueError):
            logger.exception("Memory validation failed")
            raise

        previous = None
        resolved_logical_id = uuid.UUID(str(logical_id)) if logical_id is not None else uuid.uuid4()
        if logical_id is not None:
            previous = self._repository.latest_version(resolved_logical_id)
            if previous is None:
                raise MemoryNotFoundError(f"logical memory not found: {logical_id}")
        version = previous.version + 1 if previous else 1
        created_at = payload.created_at or datetime.now(timezone.utc)
        serialized_content = self._serializer.json_safe(payload.content)
        content_hash = self._content_hash(payload, serialized_content)
        duplicate = self._repository.find_by_hash(content_hash)
        if duplicate is not None:
            logger.warning(
                "Duplicate memory rejected type=%s existing_id=%s",
                payload.memory_type,
                duplicate.id,
            )
            raise DuplicateMemoryError(f"identical memory already exists: {duplicate.id}")

        try:
            entry = self._repository.create_entry(
                logical_id=resolved_logical_id,
                version=version,
                previous_version_id=previous.id if previous else None,
                memory_type=payload.memory_type,
                category=self._clean(payload.category),
                title=self._clean(payload.title),
                summary=self._clean(payload.summary),
                content=serialized_content,
                content_hash=content_hash,
                channel_id=self._clean(payload.channel_id),
                video_id=self._clean(payload.video_id),
                topic=self._clean(payload.topic),
                game=self._clean(payload.game),
                status=self._clean(payload.status) or "active",
                confidence=payload.confidence,
                source_type=self._clean(payload.source_type),
                source_id=self._clean(payload.source_id),
                tags=self._deduplicate(payload.tags),
                keywords=self._deduplicate(payload.keywords),
                metadata_json=self._serializer.json_safe(payload.metadata) or None,
                created_at=created_at,
                archived_at=created_at if payload.status == "archived" else None,
                is_deleted=payload.status == "deleted",
            )
            self._repository.add_search_terms(
                entry.id, self._indexer.build_terms(payload), created_at
            )
            for relationship in relationships:
                self.link_entries(entry.id, relationship, commit=False)
            if commit:
                self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            logger.exception("Memory persistence constraint failed type=%s", payload.memory_type)
            raise DuplicateMemoryError("memory violates a uniqueness constraint") from exc
        except Exception:
            self._session.rollback()
            logger.exception("Memory creation failed type=%s", payload.memory_type)
            raise

        logger.info(
            "Memory %s id=%s logical_id=%s type=%s version=%s",
            "updated" if version > 1 else "created",
            entry.id,
            entry.logical_id,
            entry.memory_type,
            entry.version,
        )
        return self._serializer.entry(entry)

    def load_memory(self, entry_id: Any) -> dict[str, Any]:
        entry = self._repository.get_entry(entry_id)
        if entry is None:
            raise MemoryNotFoundError(f"memory not found: {entry_id}")
        return self._serializer.entry(entry)

    def search_memory(self, query: MemorySearchQuery | dict[str, Any]) -> dict[str, Any]:
        resolved = query if isinstance(query, MemorySearchQuery) else MemorySearchQuery(**query)
        result = self._search.search(resolved)
        logger.info(
            "Memory search completed page=%s page_size=%s total=%s",
            resolved.page,
            resolved.page_size,
            result["pagination"]["total"],
        )
        return result

    def get_history(self, logical_id: Any, *, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        self._validate_page(page, page_size)
        entries = self._repository.get_history(
            logical_id, offset=(page - 1) * page_size, limit=page_size
        )
        return {"logical_id": str(logical_id), "items": [self._serializer.entry(item) for item in entries]}

    def get_video_history(self, video_id: str, *, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        self._validate_page(page, page_size)
        entries = self._repository.get_video_history(
            video_id, offset=(page - 1) * page_size, limit=page_size
        )
        return {"video_id": video_id, "items": [self._serializer.entry(item) for item in entries]}

    def get_prediction_history(self, *, video_id: str | None = None, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        return self._get_type_history("prediction", video_id, page, page_size)

    def get_recommendation_history(self, *, video_id: str | None = None, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        return self._get_type_history("recommendation", video_id, page, page_size)

    def get_related_entries(self, entry_id: Any) -> dict[str, Any]:
        if self._repository.get_entry(entry_id) is None:
            raise MemoryNotFoundError(f"memory not found: {entry_id}")
        items = []
        for relationship, related in self._repository.get_relationships(entry_id):
            serialized = self._serializer.relationship(relationship, related)
            serialized["direction"] = (
                "outgoing" if str(relationship.source_entry_id) == str(entry_id) else "incoming"
            )
            items.append(serialized)
        return {"entry_id": str(entry_id), "relationships": items}

    def link_entries(
        self,
        source_entry_id: Any,
        relationship: RelationshipInput,
        *,
        commit: bool = True,
    ) -> dict[str, Any]:
        relationship = self._validator.validate_relationship(relationship, source_entry_id)
        if self._repository.get_entry(source_entry_id) is None:
            raise MemoryNotFoundError(f"source memory not found: {source_entry_id}")
        if self._repository.get_entry(relationship.target_entry_id) is None:
            raise MemoryNotFoundError(f"target memory not found: {relationship.target_entry_id}")
        if self._repository.relationship_exists(
            source_entry_id, relationship.target_entry_id, relationship.relationship_type
        ):
            raise DuplicateMemoryError("relationship already exists")
        row = self._repository.create_relationship(
            source_entry_id=source_entry_id,
            target_entry_id=relationship.target_entry_id,
            relationship_type=relationship.relationship_type.strip().lower(),
            metadata_json=self._serializer.json_safe(relationship.metadata) or None,
            created_at=datetime.now(timezone.utc),
        )
        if commit:
            self._session.commit()
        logger.info(
            "Memory relationship created source=%s target=%s type=%s",
            source_entry_id,
            relationship.target_entry_id,
            relationship.relationship_type,
        )
        return self._serializer.relationship(row)

    def archive_memory(self, logical_id: Any, *, commit: bool = True) -> dict[str, Any]:
        latest = self._require_latest(logical_id)
        if latest.status == "archived":
            raise DuplicateMemoryError("memory is already archived")
        result = self.save_memory(
            self._input_from_entry(latest, status="archived"),
            logical_id=logical_id,
            commit=commit,
        )
        logger.info("Memory archived logical_id=%s version=%s", logical_id, result["version"])
        return result

    def delete_memory(self, logical_id: Any, *, commit: bool = True) -> dict[str, Any]:
        """Soft-delete by appending a tombstone version; historical rows remain intact."""

        latest = self._require_latest(logical_id)
        if latest.is_deleted:
            raise DuplicateMemoryError("memory is already deleted")
        result = self.save_memory(
            self._input_from_entry(latest, status="deleted"),
            logical_id=logical_id,
            commit=commit,
        )
        logger.info("Memory soft-deleted logical_id=%s version=%s", logical_id, result["version"])
        return result

    def _get_type_history(self, memory_type: str, video_id: str | None, page: int, page_size: int) -> dict[str, Any]:
        self._validate_page(page, page_size)
        entries = self._repository.get_type_history(
            memory_type,
            video_id=video_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return {"memory_type": memory_type, "video_id": video_id, "items": [self._serializer.entry(item) for item in entries]}

    def _require_latest(self, logical_id: Any) -> Any:
        latest = self._repository.latest_version(logical_id)
        if latest is None:
            raise MemoryNotFoundError(f"logical memory not found: {logical_id}")
        return latest

    def _input_from_entry(self, entry: Any, *, status: str) -> MemoryInput:
        return MemoryInput(
            memory_type=entry.memory_type,
            content=entry.content,
            category=entry.category,
            title=entry.title,
            summary=entry.summary,
            channel_id=entry.channel_id,
            video_id=entry.video_id,
            topic=entry.topic,
            game=entry.game,
            status=status,
            confidence=float(entry.confidence) if entry.confidence is not None else None,
            source_type=entry.source_type,
            source_id=entry.source_id,
            tags=entry.tags or [],
            keywords=entry.keywords or [],
            metadata=entry.metadata_json or {},
        )

    def _content_hash(self, payload: MemoryInput, content: dict[str, Any]) -> str:
        canonical = {
            "memory_type": payload.memory_type,
            "content": content,
            "category": self._clean(payload.category),
            "title": self._clean(payload.title),
            "summary": self._clean(payload.summary),
            "channel_id": self._clean(payload.channel_id),
            "video_id": self._clean(payload.video_id),
            "topic": self._clean(payload.topic),
            "game": self._clean(payload.game),
            "status": self._clean(payload.status),
            "confidence": payload.confidence,
            "source_type": self._clean(payload.source_type),
            "source_id": self._clean(payload.source_id),
            "tags": sorted(self._deduplicate(payload.tags)),
            "keywords": sorted(self._deduplicate(payload.keywords)),
            "metadata": self._serializer.json_safe(payload.metadata),
        }
        rendered = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(rendered.encode("utf-8")).hexdigest()

    def _clean(self, value: str | None) -> str | None:
        cleaned = value.strip() if value else None
        return cleaned or None

    def _deduplicate(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    def _validate_page(self, page: int, page_size: int) -> None:
        self._validator.validate_search(MemorySearchQuery(page=page, page_size=page_size))
