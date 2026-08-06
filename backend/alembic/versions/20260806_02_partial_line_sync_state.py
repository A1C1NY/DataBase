"""Persist unresolved stop-line summaries for partial sync cooldowns."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "20260806_02"
down_revision: str | None = "20260805_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bus_stops",
        sa.Column("unresolved_line_summaries", mysql.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bus_stops", "unresolved_line_summaries")
