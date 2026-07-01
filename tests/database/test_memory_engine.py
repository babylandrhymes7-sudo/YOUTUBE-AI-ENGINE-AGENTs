"""Unit tests for append-only memory behavior using an isolated repository double."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from memory.contracts import MemoryInput, MemorySearchQuery, RelationshipInput
from memory.engine import DuplicateMemoryError, MemoryEngine
from memory.validator import MemoryValidationError


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeRepository:
    def __init__(self) -> None:
        self.entries: dict[uuid.UUID, SimpleNamespace] = {}
        self.terms: dict[uuid.UUID, list[dict]] = {}
        self.relationships: list[SimpleNamespace] = []

    def create_entry(self, **data):
        entry = SimpleNamespace(id=uuid.uuid4(), **data)
        self.entries[entry.id] = entry
        return entry

    def add_search_terms(self, entry_id, terms, created_at):
        self.terms[entry_id] = terms

    def find_by_hash(self, content_hash):
        return next((entry for entry in self.entries.values() if entry.content_hash == content_hash), None)

    def get_entry(self, entry_id):
        try:
            resolved = uuid.UUID(str(entry_id))
        except ValueError:
            return None
        return self.entries.get(resolved)

    def latest_version(self, logical_id):
        candidates = [entry for entry in self.entries.values() if entry.logical_id == uuid.UUID(str(logical_id))]
        return max(candidates, key=lambda entry: entry.version) if candidates else None

    def get_history(self, logical_id, offset=0, limit=100):
        entries = [entry for entry in self.entries.values() if str(entry.logical_id) == str(logical_id)]
        return sorted(entries, key=lambda entry: entry.version, reverse=True)[offset : offset + limit]

    def search(self, query, normalized_keyword=None):
        entries = list(self.entries.values())
        if query.latest_versions_only:
            latest = {}
            for entry in entries:
                if entry.logical_id not in latest or entry.version > latest[entry.logical_id].version:
                    latest[entry.logical_id] = entry
            entries = list(latest.values())
        if query.memory_type:
            entries = [entry for entry in entries if entry.memory_type == query.memory_type]
        if query.video_id:
            entries = [entry for entry in entries if entry.video_id == query.video_id]
        if normalized_keyword:
            entries = [
                entry for entry in entries
                if any(normalized_keyword in term["normalized_term"] for term in self.terms[entry.id])
            ]
        if not query.include_archived:
            entries = [entry for entry in entries if entry.archived_at is None]
        if not query.include_deleted:
            entries = [entry for entry in entries if not entry.is_deleted]
        total = len(entries)
        start = (query.page - 1) * query.page_size
        return entries[start : start + query.page_size], total

    def get_video_history(self, video_id, offset=0, limit=100):
        return [entry for entry in self.entries.values() if entry.video_id == video_id][offset : offset + limit]

    def get_type_history(self, memory_type, video_id=None, offset=0, limit=100):
        entries = [entry for entry in self.entries.values() if entry.memory_type == memory_type]
        if video_id:
            entries = [entry for entry in entries if entry.video_id == video_id]
        return entries[offset : offset + limit]

    def relationship_exists(self, source_id, target_id, relationship_type):
        return any(
            str(row.source_entry_id) == str(source_id)
            and str(row.target_entry_id) == str(target_id)
            and row.relationship_type == relationship_type
            for row in self.relationships
        )

    def create_relationship(self, **data):
        row = SimpleNamespace(id=uuid.uuid4(), **data)
        self.relationships.append(row)
        return row

    def get_relationships(self, entry_id):
        result = []
        for row in self.relationships:
            if str(row.source_entry_id) == str(entry_id):
                result.append((row, self.get_entry(row.target_entry_id)))
            elif str(row.target_entry_id) == str(entry_id):
                result.append((row, self.get_entry(row.source_entry_id)))
        return result


@pytest.fixture
def engine():
    session = FakeSession()
    repository = FakeRepository()
    return MemoryEngine(session, repository=repository), session


def recommendation(**changes) -> MemoryInput:
    values = {
        "memory_type": "recommendation",
        "content": {"outcome": "CTR increased by 14%"},
        "title": "Use a clearer thumbnail",
        "video_id": "video-1",
        "game": "Brawl Stars",
        "topic": "Kenji",
        "confidence": 0.92,
        "status": "implemented",
        "tags": ["shorts", "thumbnail"],
        "keywords": ["CTR", "Kenji"],
    }
    values.update(changes)
    return MemoryInput(**values)


def test_saving_and_loading_memory(engine) -> None:
    memory, session = engine
    saved = memory.save_memory(recommendation())

    loaded = memory.load_memory(saved["id"])
    assert loaded["version"] == 1
    assert loaded["game"] == "Brawl Stars"
    assert loaded["created_at"]
    assert session.commits == 1


def test_duplicate_detection(engine) -> None:
    memory, _ = engine
    memory.save_memory(recommendation())

    with pytest.raises(DuplicateMemoryError):
        memory.save_memory(recommendation())


def test_versioning_never_overwrites_history(engine) -> None:
    memory, _ = engine
    first = memory.save_memory(recommendation())
    second = memory.save_memory(
        recommendation(content={"outcome": "CTR increased by 20%"}),
        logical_id=first["logical_id"],
    )

    history = memory.get_history(first["logical_id"])
    assert second["version"] == 2
    assert [item["version"] for item in history["items"]] == [2, 1]
    assert history["items"][1]["content"]["outcome"] == "CTR increased by 14%"


def test_search_uses_indexed_keywords_and_pagination(engine) -> None:
    memory, _ = engine
    memory.save_memory(recommendation())
    memory.save_memory(
        recommendation(
            content={"idea": "Other"},
            title="Different",
            topic="Shelly",
            keywords=["strategy"],
        )
    )

    result = memory.search_memory(MemorySearchQuery(keyword="kenji", page=1, page_size=10))
    assert result["pagination"]["total"] == 1
    assert result["items"][0]["topic"] == "Kenji"


def test_relationships_are_bidirectionally_retrievable(engine) -> None:
    memory, _ = engine
    report = memory.save_memory(
        MemoryInput(memory_type="daily_report", content={"summary": "Daily report"})
    )
    prediction = memory.save_memory(
        MemoryInput(memory_type="prediction", content={"metric": "views", "value": 500})
    )

    memory.link_entries(
        report["id"],
        RelationshipInput(prediction["id"], "contains_prediction"),
    )

    related = memory.get_related_entries(prediction["id"])
    assert related["relationships"][0]["direction"] == "incoming"
    assert related["relationships"][0]["entry"]["memory_type"] == "daily_report"


def test_archive_and_delete_append_versions(engine) -> None:
    memory, _ = engine
    first = memory.save_memory(recommendation())
    archived = memory.archive_memory(first["logical_id"])
    deleted = memory.delete_memory(first["logical_id"])

    assert archived["version"] == 2
    assert archived["archived_at"]
    assert deleted["version"] == 3
    assert deleted["is_deleted"] is True
    assert len(memory.get_history(first["logical_id"])["items"]) == 3


def test_validation_rejects_malformed_records(engine) -> None:
    memory, _ = engine

    with pytest.raises(MemoryValidationError):
        memory.save_memory(MemoryInput(memory_type="recommendation", content={}))
    with pytest.raises(MemoryValidationError):
        memory.save_memory(recommendation(confidence=1.5))


def test_documented_flat_payload_is_normalized(engine) -> None:
    memory, _ = engine
    saved = memory.save_memory(
        {
            "memory_type": "recommendation",
            "related_video": "video-9",
            "game": "Brawl Stars",
            "topic": "Kenji",
            "confidence": 0.92,
            "status": "implemented",
            "outcome": "CTR increased by 14%",
            "related_reports": ["report-1"],
            "related_predictions": ["prediction-1"],
            "tags": ["shorts", "thumbnail"],
        }
    )

    assert saved["video_id"] == "video-9"
    assert saved["content"]["outcome"] == "CTR increased by 14%"
