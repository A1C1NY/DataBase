"""Create the nine Amap transit tables.

Revision ID: 20260805_01
Revises:
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "20260805_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=3),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(3)"),
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=3),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(3)"),
        ),
    )


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("endpoint", mysql.ENUM("stopname", "linename"), nullable=False),
        sa.Column(
            "trigger_type",
            mysql.ENUM("sample_import", "manual", "user_request"),
            nullable=False,
        ),
        sa.Column("request_keyword", sa.String(length=255), nullable=True),
        sa.Column("city_code", sa.String(length=16), nullable=True),
        sa.Column(
            "started_at",
            mysql.DATETIME(fsp=3),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(3)"),
        ),
        sa.Column("finished_at", mysql.DATETIME(fsp=3), nullable=True),
        sa.Column(
            "status",
            mysql.ENUM("running", "success", "partial", "failed"),
            nullable=False,
            server_default=sa.text("'running'"),
        ),
        sa.Column(
            "received_count",
            mysql.INTEGER(unsigned=True),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "inserted_count",
            mysql.INTEGER(unsigned=True),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "updated_count",
            mysql.INTEGER(unsigned=True),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "skipped_count",
            mysql.INTEGER(unsigned=True),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "failed_count",
            mysql.INTEGER(unsigned=True),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_ingestion_runs"),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "idx_ingestion_runs_status_started",
        "ingestion_runs",
        ["status", "started_at"],
    )
    op.create_index(
        "idx_ingestion_runs_endpoint_started",
        "ingestion_runs",
        ["endpoint", "started_at"],
    )
    op.create_index("idx_ingestion_runs_started", "ingestion_runs", ["started_at"])

    op.create_table(
        "users",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            mysql.ENUM("passenger", "analyst", "admin"),
            nullable=False,
            server_default=sa.text("'passenger'"),
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        **TABLE_OPTIONS,
    )

    op.create_table(
        "bus_stops",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("amap_stop_id", sa.String(length=64), nullable=True),
        sa.Column("stop_name", sa.String(length=150), nullable=False),
        sa.Column("normalized_name", sa.String(length=150), nullable=False),
        sa.Column("longitude", mysql.DECIMAL(10, 7), nullable=False),
        sa.Column("latitude", mysql.DECIMAL(10, 7), nullable=False),
        sa.Column(
            "coordinate_system",
            mysql.ENUM("GCJ02"),
            nullable=False,
            server_default=sa.text("'GCJ02'"),
        ),
        sa.Column("city_code", sa.String(length=16), nullable=True),
        sa.Column(
            "line_membership_status",
            mysql.ENUM("unknown", "partial", "complete"),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column("lines_checked_at", mysql.DATETIME(fsp=3), nullable=True),
        sa.Column("last_ingestion_run_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180", name=op.f("ck_bus_stops_longitude_range")
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90", name=op.f("ck_bus_stops_latitude_range")
        ),
        sa.ForeignKeyConstraint(
            ["last_ingestion_run_id"],
            ["ingestion_runs.id"],
            name="fk_bus_stops_last_ingestion_run_id_ingestion_runs",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bus_stops"),
        sa.UniqueConstraint("amap_stop_id", name="uq_bus_stops_amap_stop_id"),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "idx_bus_stops_name_active", "bus_stops", ["normalized_name", "is_active"]
    )
    op.create_index(
        "idx_bus_stops_city_name_active",
        "bus_stops",
        ["city_code", "normalized_name", "is_active"],
    )
    op.create_index(
        "idx_bus_stops_location", "bus_stops", ["longitude", "latitude"]
    )

    op.create_table(
        "bus_lines",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("amap_line_id", sa.String(length=64), nullable=False),
        sa.Column("amap_reverse_line_id", sa.String(length=64), nullable=True),
        sa.Column("line_name", sa.String(length=100), nullable=False),
        sa.Column("amap_name", sa.String(length=255), nullable=False),
        sa.Column("amap_type", sa.String(length=32), nullable=True),
        sa.Column("city_code", sa.String(length=16), nullable=True),
        sa.Column("start_stop_name", sa.String(length=150), nullable=True),
        sa.Column("end_stop_name", sa.String(length=150), nullable=True),
        sa.Column("first_departure_time", mysql.TIME(), nullable=True),
        sa.Column("last_departure_time", mysql.TIME(), nullable=True),
        sa.Column("loop_flag", sa.Boolean(), nullable=True),
        sa.Column("amap_status", sa.String(length=16), nullable=True),
        sa.Column("company_name", sa.String(length=150), nullable=True),
        sa.Column("distance_km", mysql.DECIMAL(10, 3), nullable=True),
        sa.Column("basic_price", mysql.DECIMAL(8, 2), nullable=True),
        sa.Column("total_price", mysql.DECIMAL(8, 2), nullable=True),
        sa.Column("bounds_raw", sa.String(length=255), nullable=True),
        sa.Column("polyline_raw", mysql.MEDIUMTEXT(), nullable=False),
        sa.Column("last_ingestion_run_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["last_ingestion_run_id"],
            ["ingestion_runs.id"],
            name="fk_bus_lines_last_ingestion_run_id_ingestion_runs",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bus_lines"),
        sa.UniqueConstraint("amap_line_id", name="uq_bus_lines_amap_line_id"),
        **TABLE_OPTIONS,
    )
    op.create_index("idx_bus_lines_name_active", "bus_lines", ["line_name", "is_active"])
    op.create_index(
        "idx_bus_lines_city_name_active",
        "bus_lines",
        ["city_code", "line_name", "is_active"],
    )

    op.create_table(
        "bus_line_stops",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("line_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("stop_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("sequence_no", mysql.SMALLINT(unsigned=True), nullable=False),
        sa.Column("amap_stop_id_snapshot", sa.String(length=64), nullable=True),
        sa.Column("ingestion_run_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.CheckConstraint(
            "sequence_no >= 1", name=op.f("ck_bus_line_stops_sequence_positive")
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name="fk_bus_line_stops_ingestion_run_id_ingestion_runs",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["bus_lines.id"],
            name="fk_bus_line_stops_line_id_bus_lines",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["stop_id"],
            ["bus_stops.id"],
            name="fk_bus_line_stops_stop_id_bus_stops",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bus_line_stops"),
        sa.UniqueConstraint(
            "line_id", "sequence_no", name="uq_bus_line_stops_line_sequence"
        ),
        **TABLE_OPTIONS,
    )
    op.create_index("idx_bus_line_stops_stop", "bus_line_stops", ["stop_id"])
    op.create_index(
        "idx_bus_line_stops_line_stop", "bus_line_stops", ["line_id", "stop_id"]
    )

    op.create_table(
        "bus_line_path_points",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("line_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("sequence_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("longitude", mysql.DECIMAL(10, 7), nullable=False),
        sa.Column("latitude", mysql.DECIMAL(10, 7), nullable=False),
        sa.Column(
            "coordinate_system",
            mysql.ENUM("GCJ02"),
            nullable=False,
            server_default=sa.text("'GCJ02'"),
        ),
        sa.Column("ingestion_run_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.CheckConstraint(
            "sequence_no >= 1",
            name=op.f("ck_bus_line_path_points_sequence_positive"),
        ),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180",
            name=op.f("ck_bus_line_path_points_longitude_range"),
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90",
            name=op.f("ck_bus_line_path_points_latitude_range"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name="fk_bus_line_path_points_ingestion_run_id_ingestion_runs",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["bus_lines.id"],
            name="fk_bus_line_path_points_line_id_bus_lines",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bus_line_path_points"),
        sa.UniqueConstraint(
            "line_id", "sequence_no", name="uq_bus_line_path_points_line_sequence"
        ),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "idx_bus_line_path_points_line_sequence",
        "bus_line_path_points",
        ["line_id", "sequence_no"],
    )

    op.create_table(
        "favorite_stops",
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("stop_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=3),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(3)"),
        ),
        sa.ForeignKeyConstraint(
            ["stop_id"],
            ["bus_stops.id"],
            name="fk_favorite_stops_stop_id_bus_stops",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_favorite_stops_user_id_users",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "stop_id", name="pk_favorite_stops"),
        **TABLE_OPTIONS,
    )
    op.create_index("idx_favorite_stops_stop", "favorite_stops", ["stop_id"])

    op.create_table(
        "favorite_lines",
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("line_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=3),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(3)"),
        ),
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["bus_lines.id"],
            name="fk_favorite_lines_line_id_bus_lines",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_favorite_lines_user_id_users",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "line_id", name="pk_favorite_lines"),
        **TABLE_OPTIONS,
    )
    op.create_index("idx_favorite_lines_line", "favorite_lines", ["line_id"])

    op.create_table(
        "stop_view_events",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column(
            "actor_role",
            mysql.ENUM("anonymous", "passenger", "analyst", "admin"),
            nullable=False,
        ),
        sa.Column("stop_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column(
            "entry_point",
            mysql.ENUM("search", "line_map", "favorite", "direct"),
            nullable=False,
        ),
        sa.Column(
            "viewed_at",
            mysql.DATETIME(fsp=3),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(3)"),
        ),
        sa.ForeignKeyConstraint(
            ["stop_id"],
            ["bus_stops.id"],
            name="fk_stop_view_events_stop_id_bus_stops",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_stop_view_events_user_id_users",
            onupdate="RESTRICT",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stop_view_events"),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "idx_stop_view_events_stop_time",
        "stop_view_events",
        ["stop_id", "viewed_at"],
    )
    op.create_index(
        "idx_stop_view_events_role_time",
        "stop_view_events",
        ["actor_role", "viewed_at"],
    )
    op.create_index("idx_stop_view_events_time", "stop_view_events", ["viewed_at"])


def downgrade() -> None:
    op.drop_table("stop_view_events")
    op.drop_table("favorite_lines")
    op.drop_table("favorite_stops")
    op.drop_table("bus_line_path_points")
    op.drop_table("bus_line_stops")
    op.drop_table("bus_lines")
    op.drop_table("bus_stops")
    op.drop_table("users")
    op.drop_table("ingestion_runs")
