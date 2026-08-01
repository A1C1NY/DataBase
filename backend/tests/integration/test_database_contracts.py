"""Static schema contracts matching the MySQL construction guide."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

import app.models  # noqa: F401
from app.db.base import Base

EXPECTED_COLUMNS = {
    "users": ["id", "username", "password_hash", "role", "is_active", "created_at", "updated_at"],
    "lines": [
        "id",
        "line_name",
        "direction",
        "line_type",
        "shanghai_line_id",
        "amap_line_id",
        "first_departure_time",
        "last_departure_time",
        "is_active",
        "created_at",
        "updated_at",
    ],
    "stops": [
        "id",
        "stop_name",
        "amap_stop_id",
        "longitude",
        "latitude",
        "is_active",
        "created_at",
        "updated_at",
    ],
    "line_routes": ["id", "line_id", "stop_id", "sequence_no", "shanghai_stop_id"],
    "favorite_stops": ["user_id", "stop_id", "created_at"],
    "query_logs": ["id", "user_id", "stop_id", "queried_at"],
    "ingestion_runs": [
        "id",
        "source",
        "task_type",
        "trigger_type",
        "request_key",
        "started_at",
        "finished_at",
        "status",
        "received_count",
        "inserted_count",
        "updated_count",
        "skipped_count",
        "failed_count",
        "error_message",
    ],
    "arrival_infos": [
        "id",
        "ingestion_run_id",
        "line_id",
        "stop_id",
        "source_up_down",
        "collected_at",
        "current_bus_distance_m",
        "current_bus_arrival_min",
        "current_bus_comfort",
        "current_bus_stop_count",
        "current_license_plate",
        "current_barrier_free",
        "next_bus_distance_m",
        "next_bus_arrival_min",
        "next_bus_stop_count",
        "next_license_plate",
        "next_barrier_free",
    ],
    "dispatch_schedules": [
        "id",
        "ingestion_run_id",
        "line_id",
        "collected_at",
        "schedule_code",
        "message_default",
        "message_short",
    ],
    "dispatch_cars": [
        "id",
        "schedule_id",
        "sequence_no",
        "vehicle_text",
        "is_barrier_free",
        "planned_departure_at",
        "countdown_text",
        "countdown_seconds",
    ],
}

EXPECTED_TYPES = {
    "users": [
        "BIGINT UNSIGNED",
        "VARCHAR(64)",
        "VARCHAR(255)",
        "ENUM('passenger','analyst','admin')",
        "BOOL",
        "DATETIME(3)",
        "DATETIME(3)",
    ],
    "lines": [
        "BIGINT UNSIGNED",
        "VARCHAR(100)",
        "TINYINT UNSIGNED",
        "TINYINT UNSIGNED",
        "VARCHAR(32)",
        "VARCHAR(32)",
        "TIME",
        "TIME",
        "BOOL",
        "DATETIME(3)",
        "DATETIME(3)",
    ],
    "stops": [
        "BIGINT UNSIGNED",
        "VARCHAR(150)",
        "VARCHAR(32)",
        "DECIMAL(10, 7)",
        "DECIMAL(10, 7)",
        "BOOL",
        "DATETIME(3)",
        "DATETIME(3)",
    ],
    "line_routes": [
        "BIGINT UNSIGNED",
        "BIGINT UNSIGNED",
        "BIGINT UNSIGNED",
        "SMALLINT UNSIGNED",
        "VARCHAR(32)",
    ],
    "favorite_stops": ["BIGINT UNSIGNED", "BIGINT UNSIGNED", "DATETIME(3)"],
    "query_logs": ["BIGINT UNSIGNED", "BIGINT UNSIGNED", "BIGINT UNSIGNED", "DATETIME(3)"],
    "ingestion_runs": [
        "BIGINT UNSIGNED",
        "ENUM('shanghai','amap')",
        "VARCHAR(50)",
        "ENUM('scheduled','manual','user_request')",
        "VARCHAR(255)",
        "DATETIME(3)",
        "DATETIME(3)",
        "ENUM('running','success','partial','failed')",
        "INTEGER UNSIGNED",
        "INTEGER UNSIGNED",
        "INTEGER UNSIGNED",
        "INTEGER UNSIGNED",
        "INTEGER UNSIGNED",
        "TEXT",
    ],
    "arrival_infos": [
        "BIGINT UNSIGNED",
        "BIGINT UNSIGNED",
        "BIGINT UNSIGNED",
        "BIGINT UNSIGNED",
        "TINYINT UNSIGNED",
        "DATETIME(3)",
        "INTEGER UNSIGNED",
        "INTEGER UNSIGNED",
        "TINYINT UNSIGNED",
        "SMALLINT UNSIGNED",
        "VARCHAR(64)",
        "BOOL",
        "INTEGER UNSIGNED",
        "INTEGER UNSIGNED",
        "SMALLINT UNSIGNED",
        "VARCHAR(64)",
        "BOOL",
    ],
    "dispatch_schedules": [
        "BIGINT UNSIGNED",
        "BIGINT UNSIGNED",
        "BIGINT UNSIGNED",
        "DATETIME(3)",
        "SMALLINT",
        "VARCHAR(255)",
        "VARCHAR(255)",
    ],
    "dispatch_cars": [
        "BIGINT UNSIGNED",
        "BIGINT UNSIGNED",
        "TINYINT UNSIGNED",
        "VARCHAR(64)",
        "BOOL",
        "DATETIME(3)",
        "VARCHAR(64)",
        "INTEGER UNSIGNED",
    ],
}

EXPECTED_NULLABLE = {
    "users": set(),
    "lines": {
        "line_type",
        "shanghai_line_id",
        "amap_line_id",
        "first_departure_time",
        "last_departure_time",
    },
    "stops": {"amap_stop_id"},
    "line_routes": {"shanghai_stop_id"},
    "favorite_stops": set(),
    "query_logs": {"user_id"},
    "ingestion_runs": {"request_key", "finished_at", "error_message"},
    "arrival_infos": {
        "source_up_down",
        "current_bus_distance_m",
        "current_bus_arrival_min",
        "current_bus_comfort",
        "current_bus_stop_count",
        "current_license_plate",
        "current_barrier_free",
        "next_bus_distance_m",
        "next_bus_arrival_min",
        "next_bus_stop_count",
        "next_license_plate",
        "next_barrier_free",
    },
    "dispatch_schedules": {"schedule_code", "message_default", "message_short"},
    "dispatch_cars": {
        "vehicle_text",
        "is_barrier_free",
        "planned_departure_at",
        "countdown_text",
        "countdown_seconds",
    },
}

EXPECTED_PRIMARY_KEYS = {
    "users": ["id"],
    "lines": ["id"],
    "stops": ["id"],
    "line_routes": ["id"],
    "favorite_stops": ["user_id", "stop_id"],
    "query_logs": ["id"],
    "ingestion_runs": ["id"],
    "arrival_infos": ["id"],
    "dispatch_schedules": ["id"],
    "dispatch_cars": ["id"],
}

EXPECTED_DEFAULTS = {
    "users": {
        "role": "'passenger'",
        "is_active": "1",
        "created_at": "CURRENT_TIMESTAMP(3)",
        "updated_at": "CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)",
    },
    "lines": {
        "is_active": "1",
        "created_at": "CURRENT_TIMESTAMP(3)",
        "updated_at": "CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)",
    },
    "stops": {
        "is_active": "1",
        "created_at": "CURRENT_TIMESTAMP(3)",
        "updated_at": "CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)",
    },
    "line_routes": {},
    "favorite_stops": {"created_at": "CURRENT_TIMESTAMP(3)"},
    "query_logs": {"queried_at": "CURRENT_TIMESTAMP(3)"},
    "ingestion_runs": {
        "started_at": "CURRENT_TIMESTAMP(3)",
        "status": "'running'",
        "received_count": "0",
        "inserted_count": "0",
        "updated_count": "0",
        "skipped_count": "0",
        "failed_count": "0",
    },
    "arrival_infos": {},
    "dispatch_schedules": {},
    "dispatch_cars": {},
}

EXPECTED_INDEXES = {
    "users": set(),
    "lines": {"idx_lines_name_active"},
    "stops": {"idx_stops_location", "idx_stops_name_active"},
    "line_routes": {"idx_line_routes_stop", "idx_line_routes_line_stop"},
    "favorite_stops": {"idx_favorite_stops_stop"},
    "query_logs": {
        "idx_query_logs_stop_time",
        "idx_query_logs_user_time",
        "idx_query_logs_time",
    },
    "ingestion_runs": {
        "idx_ingestion_runs_status_started",
        "idx_ingestion_runs_source_task_started",
        "idx_ingestion_runs_started",
    },
    "arrival_infos": {
        "idx_arrival_realtime",
        "idx_arrival_stop_time",
        "idx_arrival_line_time",
        "idx_arrival_time",
    },
    "dispatch_schedules": {"idx_dispatch_schedule_line_time", "idx_dispatch_schedule_time"},
    "dispatch_cars": {"idx_dispatch_cars_departure"},
}

EXPECTED_UNIQUES = {
    "users": {"uq_users_username"},
    "lines": {"uq_lines_amap_id", "uq_lines_shanghai_direction"},
    "stops": {"uq_stops_amap_id"},
    "line_routes": {"uq_line_routes_line_sequence", "uq_line_routes_shanghai_stop"},
    "favorite_stops": set(),
    "query_logs": set(),
    "ingestion_runs": set(),
    "arrival_infos": {"uq_arrival_run_line_stop"},
    "dispatch_schedules": {"uq_dispatch_schedule_run_line"},
    "dispatch_cars": {"uq_dispatch_cars_schedule_sequence"},
}

EXPECTED_CHECKS = {
    "users": set(),
    "lines": {"chk_lines_direction", "chk_lines_type"},
    "stops": {"chk_stops_longitude", "chk_stops_latitude"},
    "line_routes": {"chk_line_routes_sequence"},
    "favorite_stops": set(),
    "query_logs": set(),
    "ingestion_runs": set(),
    "arrival_infos": {"chk_arrival_source_direction", "chk_arrival_comfort"},
    "dispatch_schedules": {"chk_dispatch_schedule_code"},
    "dispatch_cars": {"chk_dispatch_cars_sequence"},
}

EXPECTED_FOREIGN_KEYS = {
    "fk_line_routes_line": ("lines.id", "RESTRICT", "RESTRICT"),
    "fk_line_routes_stop": ("stops.id", "RESTRICT", "RESTRICT"),
    "fk_favorite_stops_user": ("users.id", "CASCADE", "RESTRICT"),
    "fk_favorite_stops_stop": ("stops.id", "RESTRICT", "RESTRICT"),
    "fk_query_logs_user": ("users.id", "SET NULL", "RESTRICT"),
    "fk_query_logs_stop": ("stops.id", "RESTRICT", "RESTRICT"),
    "fk_arrival_ingestion_run": ("ingestion_runs.id", "RESTRICT", "RESTRICT"),
    "fk_arrival_line": ("lines.id", "RESTRICT", "RESTRICT"),
    "fk_arrival_stop": ("stops.id", "RESTRICT", "RESTRICT"),
    "fk_dispatch_schedule_ingestion_run": ("ingestion_runs.id", "RESTRICT", "RESTRICT"),
    "fk_dispatch_schedule_line": ("lines.id", "RESTRICT", "RESTRICT"),
    "fk_dispatch_cars_schedule": ("dispatch_schedules.id", "CASCADE", "RESTRICT"),
}


def _names(table_name: str, constraint_type: type) -> set[str]:
    return {
        constraint.name
        for constraint in Base.metadata.tables[table_name].constraints
        if isinstance(constraint, constraint_type) and constraint.name is not None
    }


def test_metadata_contains_exactly_the_ten_guide_tables() -> None:
    assert set(Base.metadata.tables) == set(EXPECTED_COLUMNS)


def test_columns_constraints_indexes_and_mysql_options_match_guide() -> None:
    dialect = mysql.dialect()
    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        table = Base.metadata.tables[table_name]
        assert list(table.columns.keys()) == expected_columns
        assert [str(column.type.compile(dialect=dialect)) for column in table.columns] == (
            EXPECTED_TYPES[table_name]
        )
        assert {column.name for column in table.columns if column.nullable} == (
            EXPECTED_NULLABLE[table_name]
        )
        assert [column.name for column in table.primary_key.columns] == EXPECTED_PRIMARY_KEYS[
            table_name
        ]
        actual_defaults = {
            column.name: str(column.server_default.arg)
            for column in table.columns
            if column.server_default is not None
        }
        assert actual_defaults == EXPECTED_DEFAULTS[table_name]
        assert {index.name for index in table.indexes} == EXPECTED_INDEXES[table_name]
        assert _names(table_name, UniqueConstraint) == EXPECTED_UNIQUES[table_name]
        assert _names(table_name, CheckConstraint) == EXPECTED_CHECKS[table_name]
        assert table.dialect_options["mysql"]["engine"] == "InnoDB"
        assert table.dialect_options["mysql"]["charset"] == "utf8mb4"
        assert table.dialect_options["mysql"]["collate"] == "utf8mb4_0900_ai_ci"
        assert any(isinstance(item, PrimaryKeyConstraint) for item in table.constraints)


def test_foreign_key_actions_match_guide() -> None:
    actual = {}
    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            if not isinstance(constraint, ForeignKeyConstraint):
                continue
            target = next(iter(constraint.elements)).target_fullname
            actual[constraint.name] = (target, constraint.ondelete, constraint.onupdate)
    assert actual == EXPECTED_FOREIGN_KEYS


def test_mysql_types_defaults_and_special_ddl_match_guide() -> None:
    dialect = mysql.dialect()
    users = Base.metadata.tables["users"]
    ingestion_runs = Base.metadata.tables["ingestion_runs"]
    arrival_infos = Base.metadata.tables["arrival_infos"]

    assert str(users.c.id.type.compile(dialect=dialect)) == "BIGINT UNSIGNED"
    assert str(users.c.created_at.type.compile(dialect=dialect)) == "DATETIME(3)"
    assert str(users.c.created_at.server_default.arg) == "CURRENT_TIMESTAMP(3)"
    assert "ON UPDATE CURRENT_TIMESTAMP(3)" in str(users.c.updated_at.server_default.arg)
    assert list(users.c.role.type.enums) == ["passenger", "analyst", "admin"]
    assert list(ingestion_runs.c.status.type.enums) == ["running", "success", "partial", "failed"]
    assert str(ingestion_runs.c.received_count.type.compile(dialect=dialect)) == "INTEGER UNSIGNED"

    arrival_indexes = {index.name: index for index in arrival_infos.indexes}
    descending_ddl = str(
        CreateIndex(arrival_indexes["idx_arrival_stop_time"]).compile(dialect=dialect)
    )
    assert "(stop_id, collected_at DESC)" in descending_ddl

    users_ddl = str(CreateTable(users).compile(dialect=dialect))
    assert "updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE" in users_ddl
    assert "ENGINE=InnoDB" in users_ddl
    assert "CHARSET=utf8mb4" in users_ddl
    assert "COLLATE utf8mb4_0900_ai_ci" in users_ddl


def test_line_route_line_stop_index_is_not_unique() -> None:
    table = Base.metadata.tables["line_routes"]
    index = next(item for item in table.indexes if item.name == "idx_line_routes_line_stop")
    assert index.unique is False
