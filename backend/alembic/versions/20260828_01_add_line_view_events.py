"""Record bus-line detail views for analytics."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260828_01"
down_revision: str | None = "20260806_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "line_view_events",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "actor_role",
            mysql.ENUM("anonymous", "passenger", "analyst", "admin"),
            nullable=False,
        ),
        sa.Column("line_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "entry_point",
            mysql.ENUM("search", "favorite", "direct"),
            nullable=False,
        ),
        sa.Column(
            "viewed_at",
            mysql.DATETIME(fsp=3),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(3)"),
        ),
        sa.ForeignKeyConstraint(
            ["line_id"], ["bus_lines.id"],
            name="fk_line_view_events_line_id_bus_lines",
            onupdate="RESTRICT", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_line_view_events_user_id_users",
            onupdate="RESTRICT", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_line_view_events"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_line_view_events_line_time", "line_view_events", ["line_id", "viewed_at"])
    op.create_index("idx_line_view_events_role_time", "line_view_events", ["actor_role", "viewed_at"])
    op.create_index("idx_line_view_events_time", "line_view_events", ["viewed_at"])


def downgrade() -> None:
    op.drop_table("line_view_events")
