"""Store the optional Amap bus line UI color."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_04"
down_revision: str | None = "20260806_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bus_lines",
        sa.Column("ui_color", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bus_lines", "ui_color")
