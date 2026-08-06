"""Record dedicated Amap bus line ID ingestion requests."""

from collections.abc import Sequence

from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "20260806_03"
down_revision: str | None = "20260806_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "ingestion_runs",
        "endpoint",
        existing_type=mysql.ENUM("stopname", "linename"),
        type_=mysql.ENUM("stopname", "linename", "lineid"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute("UPDATE ingestion_runs SET endpoint = 'linename' WHERE endpoint = 'lineid'")
    op.alter_column(
        "ingestion_runs",
        "endpoint",
        existing_type=mysql.ENUM("stopname", "linename", "lineid"),
        type_=mysql.ENUM("stopname", "linename"),
        existing_nullable=False,
    )
