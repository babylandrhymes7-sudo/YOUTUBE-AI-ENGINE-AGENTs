"""Add append-only canonical Report Engine tables."""

from __future__ import annotations

from alembic import op

from database.models.report_engine import IntelligenceReport, IntelligenceReportSection


revision = "0004_report_engine"
down_revision = "0003_memory_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (IntelligenceReport.__table__, IntelligenceReportSection.__table__):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in (IntelligenceReportSection.__table__, IntelligenceReport.__table__):
        table.drop(bind=bind, checkfirst=True)
