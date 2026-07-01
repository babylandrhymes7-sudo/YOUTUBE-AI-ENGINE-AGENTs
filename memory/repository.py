"""Efficient PostgreSQL persistence and history queries for memory."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from .contracts import MemorySearchQuery


class MemoryRepository:
    """Persist immutable memory versions and execute paginated indexed queries."""

    def __init__(self, session: Session) -> None:
        self.session = session
        from database.models.memory_engine import MemoryEntry, MemoryRelationship, MemorySearchTerm

        self.Entry = MemoryEntry
        self.Relationship = MemoryRelationship
        self.SearchTerm = MemorySearchTerm

    def create_entry(self, **data: Any) -> Any:
        entry = self.Entry(**data)
        self.session.add(entry)
        self.session.flush()
        return entry

    def add_search_terms(self, entry_id: Any, terms: list[dict[str, str]], created_at: datetime) -> None:
        self.session.add_all(
            [self.SearchTerm(entry_id=entry_id, created_at=created_at, **term) for term in terms]
        )
        self.session.flush()

    def create_relationship(self, **data: Any) -> Any:
        relationship = self.Relationship(**data)
        self.session.add(relationship)
        self.session.flush()
        return relationship

    def get_entry(self, entry_id: Any) -> Any | None:
        return self.session.get(self.Entry, entry_id)

    def find_by_hash(self, content_hash: str) -> Any | None:
        return self.session.scalars(
            select(self.Entry).where(self.Entry.content_hash == content_hash)
        ).first()

    def latest_version(self, logical_id: Any) -> Any | None:
        statement = (
            select(self.Entry)
            .where(self.Entry.logical_id == logical_id)
            .order_by(self.Entry.version.desc())
            .limit(1)
        )
        return self.session.scalars(statement).first()

    def get_history(self, logical_id: Any, *, offset: int = 0, limit: int = 100) -> list[Any]:
        statement = (
            select(self.Entry)
            .where(self.Entry.logical_id == logical_id)
            .order_by(self.Entry.version.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def search(self, query: MemorySearchQuery, normalized_keyword: str | None = None) -> tuple[list[Any], int]:
        Entry = self.Entry
        statement = select(Entry)
        conditions = []
        if query.latest_versions_only:
            latest = (
                select(
                    Entry.logical_id.label("logical_id"),
                    func.max(Entry.version).label("latest_version"),
                )
                .group_by(Entry.logical_id)
                .subquery()
            )
            statement = statement.join(
                latest,
                and_(
                    Entry.logical_id == latest.c.logical_id,
                    Entry.version == latest.c.latest_version,
                ),
            )
        if query.date_from:
            conditions.append(Entry.created_at >= query.date_from)
        if query.date_to:
            conditions.append(Entry.created_at <= query.date_to)
        for column, value in (
            (Entry.video_id, query.video_id),
            (Entry.topic, query.topic),
            (Entry.game, query.game),
            (Entry.memory_type, query.memory_type),
            (Entry.category, query.category),
            (Entry.status, query.status),
        ):
            if value is not None:
                conditions.append(func.lower(column) == value.lower())
        if not query.include_archived:
            conditions.append(Entry.archived_at.is_(None))
        if not query.include_deleted:
            conditions.append(Entry.is_deleted.is_(False))
        term_filters = [
            ("keyword", normalized_keyword),
            ("recommendation", query.recommendation.lower() if query.recommendation else None),
            ("prediction", query.prediction.lower() if query.prediction else None),
            ("competitor", query.competitor.lower() if query.competitor else None),
            ("report", query.report.lower() if query.report else None),
        ]
        for term_kind, normalized in term_filters:
            if normalized:
                matching_term = aliased(self.SearchTerm)
                conditions.append(
                    select(matching_term.id)
                    .where(
                        matching_term.entry_id == Entry.id,
                        matching_term.normalized_term.contains(normalized),
                    )
                    .exists()
                )
        if conditions:
            statement = statement.where(*conditions)
        count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
        total = int(self.session.scalar(count_statement) or 0)
        page_statement = (
            statement.order_by(Entry.created_at.desc(), Entry.id)
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        return list(self.session.scalars(page_statement)), total

    def get_type_history(
        self,
        memory_type: str,
        *,
        video_id: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Any]:
        Entry = self.Entry
        statement = select(Entry).where(
            Entry.memory_type == memory_type,
            Entry.is_deleted.is_(False),
        )
        if video_id is not None:
            statement = statement.where(Entry.video_id == video_id)
        return list(
            self.session.scalars(
                statement.order_by(Entry.created_at.desc()).offset(offset).limit(limit)
            )
        )

    def get_video_history(self, video_id: str, *, offset: int = 0, limit: int = 100) -> list[Any]:
        Entry = self.Entry
        statement = (
            select(Entry)
            .where(Entry.video_id == video_id, Entry.is_deleted.is_(False))
            .order_by(Entry.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def get_relationships(self, entry_id: Any) -> list[tuple[Any, Any]]:
        Relationship, Entry = self.Relationship, self.Entry
        outgoing = (
            select(Relationship, Entry)
            .join(Entry, Entry.id == Relationship.target_entry_id)
            .where(Relationship.source_entry_id == entry_id)
        )
        incoming = (
            select(Relationship, Entry)
            .join(Entry, Entry.id == Relationship.source_entry_id)
            .where(Relationship.target_entry_id == entry_id)
        )
        return list(self.session.execute(outgoing).all()) + list(self.session.execute(incoming).all())

    def relationship_exists(self, source_id: Any, target_id: Any, relationship_type: str) -> bool:
        Relationship = self.Relationship
        statement = select(Relationship.id).where(
            Relationship.source_entry_id == source_id,
            Relationship.target_entry_id == target_id,
            Relationship.relationship_type == relationship_type,
        )
        return self.session.scalar(statement) is not None
