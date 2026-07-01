"""Append-only historical memory models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, UUIDPrimaryKeyMixin


class MemoryEntry(UUIDPrimaryKeyMixin, Base):
    """One immutable version of a logical memory record."""

    __tablename__ = "memory_entries"
    __table_args__ = (
        UniqueConstraint("logical_id", "version", name="uq_memory_entries_logical_version"),
        UniqueConstraint("content_hash", name="uq_memory_entries_content_hash"),
        CheckConstraint("version > 0", name="memory_entry_version_positive"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="memory_entry_confidence_range"),
        Index("ix_memory_entries_created_at", "created_at"),
        Index("ix_memory_entries_type_created", "memory_type", "created_at"),
        Index("ix_memory_entries_video_created", "video_id", "created_at"),
        Index("ix_memory_entries_category_created", "category", "created_at"),
        Index("ix_memory_entries_topic", "topic"),
        Index("ix_memory_entries_game", "game"),
        Index("ix_memory_entries_logical_version", "logical_id", "version"),
        Index("ix_memory_entries_source", "source_type", "source_id"),
    )

    logical_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memory_entries.id", ondelete="RESTRICT"), nullable=True
    )
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    channel_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    video_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    game: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    previous_version: Mapped["MemoryEntry | None"] = relationship(remote_side="MemoryEntry.id")
    outgoing_relationships: Mapped[list["MemoryRelationship"]] = relationship(
        foreign_keys="MemoryRelationship.source_entry_id",
        back_populates="source_entry",
        cascade="all, delete-orphan",
    )
    incoming_relationships: Mapped[list["MemoryRelationship"]] = relationship(
        foreign_keys="MemoryRelationship.target_entry_id",
        back_populates="target_entry",
        cascade="all, delete-orphan",
    )
    search_terms: Mapped[list["MemorySearchTerm"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )


class MemoryRelationship(UUIDPrimaryKeyMixin, Base):
    """A typed, timestamped edge between two immutable memory versions."""

    __tablename__ = "memory_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_entry_id", "target_entry_id", "relationship_type",
            name="uq_memory_relationship_edge",
        ),
        CheckConstraint("source_entry_id <> target_entry_id", name="memory_relationship_not_self"),
        Index("ix_memory_relationships_source", "source_entry_id", "created_at"),
        Index("ix_memory_relationships_target", "target_entry_id", "created_at"),
        Index("ix_memory_relationships_type", "relationship_type"),
    )

    source_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memory_entries.id", ondelete="CASCADE"), nullable=False
    )
    target_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memory_entries.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    source_entry: Mapped["MemoryEntry"] = relationship(
        foreign_keys=[source_entry_id], back_populates="outgoing_relationships"
    )
    target_entry: Mapped["MemoryEntry"] = relationship(
        foreign_keys=[target_entry_id], back_populates="incoming_relationships"
    )


class MemorySearchTerm(UUIDPrimaryKeyMixin, Base):
    """Normalized local search index term for one memory version."""

    __tablename__ = "memory_search_index"
    __table_args__ = (
        UniqueConstraint("entry_id", "term_type", "normalized_term", name="uq_memory_search_term"),
        Index("ix_memory_search_normalized", "normalized_term", "term_type"),
        Index("ix_memory_search_entry", "entry_id"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memory_entries.id", ondelete="CASCADE"), nullable=False
    )
    term: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_term: Mapped[str] = mapped_column(String(255), nullable=False)
    term_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    entry: Mapped["MemoryEntry"] = relationship(back_populates="search_terms")
