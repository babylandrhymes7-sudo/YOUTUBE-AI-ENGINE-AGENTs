"""Initial database schema for YOUTUBE AI AGENT.

TODO: Keep the first migration aligned with the ORM metadata in database.models.
"""

from __future__ import annotations

from alembic import op

from database.base import Base
import database.models  # noqa: F401


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the full normalized schema from the ORM metadata."""

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop the full normalized schema during rollback."""

    Base.metadata.drop_all(bind=op.get_bind())
