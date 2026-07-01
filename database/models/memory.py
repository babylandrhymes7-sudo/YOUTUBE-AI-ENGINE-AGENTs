"""Memory model.

TODO: Keep local AI memory records normalized and reusable across workflows.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Memory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
	"""Persist durable local memory snippets used by the AI layer."""

	__tablename__ = "memory"
	__table_args__ = (
		Index("ix_memory_memory_key", "memory_key", unique=True),
		Index("ix_memory_namespace", "namespace"),
		Index("ix_memory_is_active", "is_active"),
	)

	memory_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
	namespace: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
	content: Mapped[str] = mapped_column(Text, nullable=False)
	content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="text")
	source: Mapped[str | None] = mapped_column(String(128), nullable=True)
	metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

