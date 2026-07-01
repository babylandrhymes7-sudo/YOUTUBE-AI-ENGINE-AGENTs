"""Add append-only Memory Engine tables."""

from __future__ import annotations

from alembic import op

from database.models.memory_engine import MemoryEntry, MemoryRelationship, MemorySearchTerm


revision = "0003_memory_engine"
down_revision = "0002_graph_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (MemoryEntry.__table__, MemoryRelationship.__table__, MemorySearchTerm.__table__):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in (MemorySearchTerm.__table__, MemoryRelationship.__table__, MemoryEntry.__table__):
        table.drop(bind=bind, checkfirst=True)
