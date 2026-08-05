from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_alembic_has_one_initial_revision() -> None:
    config = Config(BACKEND_ROOT / "alembic.ini")
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())

    assert script.get_heads() == ["20260805_01"]
    assert len(revisions) == 1
    assert revisions[0].down_revision is None


def test_initial_migration_names_all_nine_tables() -> None:
    migration = (
        BACKEND_ROOT
        / "alembic"
        / "versions"
        / "20260805_01_create_amap_transit_tables.py"
    ).read_text(encoding="utf-8")
    expected_tables = {
        "ingestion_runs",
        "users",
        "bus_stops",
        "bus_lines",
        "bus_line_stops",
        "bus_line_path_points",
        "favorite_stops",
        "favorite_lines",
        "stop_view_events",
    }

    for table_name in expected_tables:
        assert f'"{table_name}"' in migration


def test_downgrade_drops_tables_directly_in_reverse_dependency_order() -> None:
    migration = (
        BACKEND_ROOT
        / "alembic"
        / "versions"
        / "20260805_01_create_amap_transit_tables.py"
    ).read_text(encoding="utf-8")
    downgrade = migration.split("def downgrade() -> None:", maxsplit=1)[1]
    expected_order = [
        "stop_view_events",
        "favorite_lines",
        "favorite_stops",
        "bus_line_path_points",
        "bus_line_stops",
        "bus_lines",
        "bus_stops",
        "users",
        "ingestion_runs",
    ]

    assert "op.drop_index" not in downgrade
    positions = [downgrade.index(f'op.drop_table("{table}")') for table in expected_order]
    assert positions == sorted(positions)
