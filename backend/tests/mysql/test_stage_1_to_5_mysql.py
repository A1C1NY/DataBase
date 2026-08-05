import json
import os
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.core.config import get_settings
from app.models.ingestion import IngestionRun
from app.models.transit import BusLine, BusLinePathPoint, BusLineStop, BusStop
from app.services.ingestion import IngestionError, IngestionService

pytestmark = pytest.mark.mysql
BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_ROOT.parent


@pytest.fixture(scope="module")
def database_url() -> str:
    url = os.getenv("TRANSIT_TEST_DATABASE_URL")
    if not url:
        pytest.skip("未配置 TRANSIT_TEST_DATABASE_URL")
    if "replace_with" in url.lower():
        pytest.fail("TRANSIT_TEST_DATABASE_URL 仍包含占位值，请使用真实测试密码")
    database_name = make_url(url).database
    if database_name is None or "test" not in database_name.lower():
        pytest.fail("TRANSIT_TEST_DATABASE_URL 的数据库名称必须明显包含 test")
    return url


@pytest.fixture(scope="module")
def engine(database_url: str):  # type: ignore[no-untyped-def]
    engine = create_engine(database_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module", autouse=True)
def migrate(database_url: str) -> None:
    previous_url = os.environ.get("TRANSIT_DATABASE_URL")
    previous_secret = os.environ.get("TRANSIT_JWT_SECRET")
    os.environ["TRANSIT_DATABASE_URL"] = database_url
    os.environ["TRANSIT_JWT_SECRET"] = "mysql-test-secret-with-at-least-32-characters"
    get_settings.cache_clear()
    config = Config(BACKEND_ROOT / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        get_settings.cache_clear()
        if previous_url is None:
            os.environ.pop("TRANSIT_DATABASE_URL", None)
        else:
            os.environ["TRANSIT_DATABASE_URL"] = previous_url
        if previous_secret is None:
            os.environ.pop("TRANSIT_JWT_SECRET", None)
        else:
            os.environ["TRANSIT_JWT_SECRET"] = previous_secret


def _payload(filename: str) -> dict[str, object]:
    payload = json.loads((REPOSITORY_ROOT / filename).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _counts(session: Session) -> tuple[int, int, int, int]:
    return (
        session.scalar(select(func.count()).select_from(BusStop)) or 0,
        session.scalar(select(func.count()).select_from(BusLine)) or 0,
        session.scalar(select(func.count()).select_from(BusLineStop)) or 0,
        session.scalar(select(func.count()).select_from(BusLinePathPoint)) or 0,
    )


def _import_all_samples(service: IngestionService) -> None:
    for filename in ("bus_stop_by_name.json", "bus_stop_raw_gaode.json"):
        outcome = service.import_stop_response(
            _payload(filename),
            trigger_type="sample_import",
            request_keyword=Path(filename).stem,
            city_code="021",
        )
        assert outcome.status == "success"
    outcome = service.import_line_response(
        _payload("bus_line_raw_gaode.json"),
        trigger_type="sample_import",
        request_keyword="bus_line_raw_gaode",
        city_code="021",
    )
    assert outcome.status == "success"


def test_mysql_session_and_schema(engine) -> None:  # type: ignore[no-untyped-def]
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1

    assert set(inspect(engine).get_table_names()) >= {
        "users",
        "bus_stops",
        "bus_lines",
        "bus_line_stops",
        "bus_line_path_points",
        "favorite_stops",
        "favorite_lines",
        "stop_view_events",
        "ingestion_runs",
    }


def test_sample_import_conflict_and_rollback(engine, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    service = IngestionService(factory)

    _import_all_samples(service)

    with factory() as session:
        first_counts = _counts(session)

    _import_all_samples(service)

    with factory() as session:
        second_counts = _counts(session)
        run_count = session.scalar(select(func.count()).select_from(IngestionRun)) or 0

    assert first_counts == (36, 2, 58, 743)
    assert second_counts == first_counts
    assert run_count == 6

    with factory.begin() as session:
        session.add_all(
            [
                BusStop(
                    stop_name="冲突测试站",
                    normalized_name="冲突测试站",
                    longitude=Decimal("121.5000000"),
                    latitude=Decimal("31.2000000"),
                    city_code="021",
                ),
                BusStop(
                    stop_name="冲突测试站",
                    normalized_name="冲突测试站",
                    longitude=Decimal("121.5001000"),
                    latitude=Decimal("31.2000000"),
                    city_code="021",
                ),
            ]
        )

    with factory() as session:
        count_before_conflict = _counts(session)[0]

    conflict = service.import_stop_response(
        {
            "status": "1",
            "busstops": [
                {
                    "name": "冲突测试站",
                    "location": "121.5000500,31.2000000",
                    "citycode": "021",
                }
            ],
        },
        trigger_type="manual",
        request_keyword="冲突测试站",
        city_code="021",
    )
    assert conflict.status == "partial"
    assert conflict.stats.skipped_count == 1
    assert conflict.stats.failed_count == 1

    with factory() as session:
        assert _counts(session)[0] == count_before_conflict
        conflict_run = session.get(IngestionRun, conflict.ingestion_run_id)
        assert conflict_run is not None
        assert conflict_run.status == "partial"
        assert conflict_run.error_message is not None
        assert "多个候选" in conflict_run.error_message
        counts_before_rollback = _counts(session)

    original_upsert_stop = service._upsert_stop
    call_count = 0

    def fail_on_second_stop(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal call_count
        result = original_upsert_stop(*args, **kwargs)
        call_count += 1
        if call_count == 2:
            raise RuntimeError("forced rollback test")
        return result

    monkeypatch.setattr(service, "_upsert_stop", fail_on_second_stop)
    with pytest.raises(IngestionError, match="入库失败"):
        service.import_line_response(
            _payload("bus_line_raw_gaode.json"),
            trigger_type="manual",
            request_keyword="forced_rollback",
            city_code="021",
        )

    with factory() as session:
        assert _counts(session) == counts_before_rollback
        failed_run = session.scalar(
            select(IngestionRun)
            .where(IngestionRun.request_keyword == "forced_rollback")
            .order_by(IngestionRun.id.desc())
        )
        assert failed_run is not None
        assert failed_run.status == "failed"
        assert failed_run.error_message is not None
        assert "forced rollback test" in failed_run.error_message
