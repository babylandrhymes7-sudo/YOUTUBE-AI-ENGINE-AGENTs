"""Add normalized graph intelligence tables."""

from __future__ import annotations

from alembic import op

from database.models.graphs import Graph, GraphEvent, GraphPoint, GraphStatistics


revision = "0002_graph_intelligence"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (Graph.__table__, GraphPoint.__table__, GraphStatistics.__table__, GraphEvent.__table__):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in (GraphEvent.__table__, GraphStatistics.__table__, GraphPoint.__table__, Graph.__table__):
        table.drop(bind=bind, checkfirst=True)
