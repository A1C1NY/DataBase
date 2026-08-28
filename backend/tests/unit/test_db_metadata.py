from sqlalchemy.dialects import mysql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

import app.models  # noqa: F401
from app.db.base import Base

EXPECTED_TABLES = {
    "bus_line_path_points",
    "bus_line_stops",
    "bus_lines",
    "bus_stops",
    "favorite_lines",
    "favorite_stops",
    "ingestion_runs",
    "stop_view_events",
    "line_view_events",
    "users",
}

EXPECTED_COLUMNS = {
    "users": {
        "id",
        "username",
        "password_hash",
        "role",
        "is_active",
        "created_at",
        "updated_at",
    },
    "bus_stops": {
        "id",
        "amap_stop_id",
        "stop_name",
        "normalized_name",
        "longitude",
        "latitude",
        "coordinate_system",
        "city_code",
        "line_membership_status",
        "lines_checked_at",
        "unresolved_line_summaries",
        "last_ingestion_run_id",
        "is_active",
        "created_at",
        "updated_at",
    },
    "bus_lines": {
        "id",
        "amap_line_id",
        "amap_reverse_line_id",
        "line_name",
        "amap_name",
        "amap_type",
        "city_code",
        "start_stop_name",
        "end_stop_name",
        "first_departure_time",
        "last_departure_time",
        "loop_flag",
        "amap_status",
        "company_name",
        "distance_km",
        "basic_price",
        "total_price",
        "bounds_raw",
        "ui_color",
        "polyline_raw",
        "last_ingestion_run_id",
        "is_active",
        "created_at",
        "updated_at",
    },
    "bus_line_stops": {
        "id",
        "line_id",
        "stop_id",
        "sequence_no",
        "amap_stop_id_snapshot",
        "ingestion_run_id",
    },
    "bus_line_path_points": {
        "id",
        "line_id",
        "sequence_no",
        "longitude",
        "latitude",
        "coordinate_system",
        "ingestion_run_id",
    },
    "favorite_stops": {"user_id", "stop_id", "created_at"},
    "favorite_lines": {"user_id", "line_id", "created_at"},
    "stop_view_events": {
        "id",
        "user_id",
        "actor_role",
        "stop_id",
        "entry_point",
        "viewed_at",
    },
    "line_view_events": {
        "id",
        "user_id",
        "actor_role",
        "line_id",
        "entry_point",
        "viewed_at",
    },
    "ingestion_runs": {
        "id",
        "endpoint",
        "trigger_type",
        "request_keyword",
        "city_code",
        "started_at",
        "finished_at",
        "status",
        "received_count",
        "inserted_count",
        "updated_count",
        "skipped_count",
        "failed_count",
        "error_message",
    },
}

EXPECTED_NULLABLE_COLUMNS = {
    "users": set(),
    "bus_stops": {
        "amap_stop_id",
        "city_code",
        "lines_checked_at",
        "unresolved_line_summaries",
        "last_ingestion_run_id",
    },
    "bus_lines": {
        "amap_reverse_line_id",
        "amap_type",
        "city_code",
        "start_stop_name",
        "end_stop_name",
        "first_departure_time",
        "last_departure_time",
        "loop_flag",
        "amap_status",
        "company_name",
        "distance_km",
        "basic_price",
        "total_price",
        "bounds_raw",
        "ui_color",
        "last_ingestion_run_id",
    },
    "bus_line_stops": {"amap_stop_id_snapshot"},
    "bus_line_path_points": set(),
    "favorite_stops": set(),
    "favorite_lines": set(),
    "stop_view_events": {"user_id"},
    "line_view_events": {"user_id"},
    "ingestion_runs": {
        "request_keyword",
        "city_code",
        "finished_at",
        "error_message",
    },
}

EXPECTED_PRIMARY_KEYS = {
    "users": ("id",),
    "bus_stops": ("id",),
    "bus_lines": ("id",),
    "bus_line_stops": ("id",),
    "bus_line_path_points": ("id",),
    "favorite_stops": ("user_id", "stop_id"),
    "favorite_lines": ("user_id", "line_id"),
    "stop_view_events": ("id",),
    "line_view_events": ("id",),
    "ingestion_runs": ("id",),
}

EXPECTED_INDEXES = {
    "users": set(),
    "bus_stops": {
        "idx_bus_stops_name_active",
        "idx_bus_stops_city_name_active",
        "idx_bus_stops_location",
    },
    "bus_lines": {"idx_bus_lines_name_active", "idx_bus_lines_city_name_active"},
    "bus_line_stops": {
        "idx_bus_line_stops_stop",
        "idx_bus_line_stops_line_stop",
    },
    "bus_line_path_points": {"idx_bus_line_path_points_line_sequence"},
    "favorite_stops": {"idx_favorite_stops_stop"},
    "favorite_lines": {"idx_favorite_lines_line"},
    "stop_view_events": {
        "idx_stop_view_events_stop_time",
        "idx_stop_view_events_role_time",
        "idx_stop_view_events_time",
    },
    "line_view_events": {
        "idx_line_view_events_line_time",
        "idx_line_view_events_role_time",
        "idx_line_view_events_time",
    },
    "ingestion_runs": {
        "idx_ingestion_runs_status_started",
        "idx_ingestion_runs_endpoint_started",
        "idx_ingestion_runs_started",
    },
}


def test_metadata_contains_exactly_the_planned_tables() -> None:
    configure_mappers()
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_each_table_has_exact_columns_nullability_primary_key_and_indexes() -> None:
    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        table = Base.metadata.tables[table_name]
        assert set(table.columns.keys()) == expected_columns
        assert {column.name for column in table.columns if column.nullable} == (
            EXPECTED_NULLABLE_COLUMNS[table_name]
        )
        assert tuple(column.name for column in table.primary_key.columns) == (
            EXPECTED_PRIMARY_KEYS[table_name]
        )
        assert {index.name for index in table.indexes} == EXPECTED_INDEXES[table_name]


def test_critical_mysql_column_types_and_defaults() -> None:
    dialect = mysql.dialect()

    for table in Base.metadata.tables.values():
        for column in table.primary_key.columns:
            assert column.type.compile(dialect=dialect) == "BIGINT UNSIGNED"

    for table_name in ("bus_stops", "bus_line_path_points"):
        table = Base.metadata.tables[table_name]
        assert table.c.longitude.type.compile(dialect=dialect) == "DECIMAL(10, 7)"
        assert table.c.latitude.type.compile(dialect=dialect) == "DECIMAL(10, 7)"
        assert str(table.c.coordinate_system.server_default.arg) == "'GCJ02'"

    assert (
        Base.metadata.tables["bus_lines"].c.polyline_raw.type.compile(dialect=dialect)
        == "MEDIUMTEXT"
    )
    assert (
        Base.metadata.tables["bus_line_stops"].c.sequence_no.type.compile(
            dialect=dialect
        )
        == "SMALLINT UNSIGNED"
    )
    assert (
        Base.metadata.tables["bus_line_path_points"].c.sequence_no.type.compile(
            dialect=dialect
        )
        == "INTEGER UNSIGNED"
    )

    for table_name in ("users", "bus_stops", "bus_lines"):
        table = Base.metadata.tables[table_name]
        assert table.c.created_at.type.compile(dialect=dialect) == "DATETIME(3)"
        assert table.c.updated_at.type.compile(dialect=dialect) == "DATETIME(3)"


def test_critical_unique_constraints_are_present() -> None:
    expected = {
        "bus_stops": {"uq_bus_stops_amap_stop_id"},
        "bus_lines": {"uq_bus_lines_amap_line_id"},
        "bus_line_stops": {"uq_bus_line_stops_line_sequence"},
        "bus_line_path_points": {"uq_bus_line_path_points_line_sequence"},
        "users": {"uq_users_username"},
    }

    for table_name, names in expected.items():
        actual = {constraint.name for constraint in Base.metadata.tables[table_name].constraints}
        assert names <= actual


def test_all_foreign_keys_have_explicit_delete_and_update_actions() -> None:
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.ondelete in {"CASCADE", "RESTRICT", "SET NULL"}
            assert foreign_key.onupdate == "RESTRICT"


def test_mysql_ddl_uses_required_engine_charset_and_unsigned_ids() -> None:
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))
        assert "ENGINE=InnoDB" in ddl
        assert "CHARSET=utf8mb4" in ddl
        assert "COLLATE utf8mb4_0900_ai_ci" in ddl

    users_ddl = str(
        CreateTable(Base.metadata.tables["users"]).compile(dialect=mysql.dialect())
    )
    assert "BIGINT UNSIGNED" in users_ddl


def test_route_membership_does_not_require_unique_line_and_stop() -> None:
    table = Base.metadata.tables["bus_line_stops"]
    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("line_id", "stop_id") not in unique_column_sets
    assert ("line_id", "sequence_no") in unique_column_sets
