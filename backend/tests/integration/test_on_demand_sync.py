"""Integration coverage for the on-demand Amap line-ID workflow."""

from __future__ import annotations

import os
from contextlib import AbstractContextManager
from typing import Any, Self

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.integrations.amap.client import AmapClient
from app.models.ingestion import IngestionRun
from app.models.transit import BusLine, BusLinePathPoint, BusLineStop, BusStop
from app.services.ingestion import (
    ImportOutcome,
    ImportStats,
    IngestionError,
    IngestionService,
)
from app.services.on_demand_sync import (
    OnDemandSyncService,
    TransitNotFound,
    TransitUpstreamError,
)
from app.services.transit import TransitService


class _EmptySession(AbstractContextManager["_EmptySession"]):
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def scalar(self, statement: object) -> None:
        return None


class _EmptyFactory:
    def __call__(self) -> _EmptySession:
        return _EmptySession()


class _IngestionTracker:
    def __init__(self, expected_endpoint: str = "lineid") -> None:
        self.failed: list[tuple[int, str]] = []
        self.expected_endpoint = expected_endpoint

    def _create_run(self, **kwargs: object) -> int:
        assert kwargs["endpoint"] == self.expected_endpoint
        return 901

    def _finish_failed_run(self, run_id: int, error: Exception, **kwargs: object) -> None:
        self.failed.append((run_id, str(error)))

    def import_line_response(self, *args: object, **kwargs: object) -> ImportOutcome:
        return ImportOutcome(901, "success", ImportStats(received_count=0))


def _settings(*, api_key: str | None = "test-amap-key") -> Settings:
    return Settings(
        _env_file=None,
        database_url="mysql+pymysql://user:password@127.0.0.1/test",
        jwt_secret="test-secret-with-at-least-32-characters",
        amap_api_key=api_key,
        amap_min_request_interval_seconds=0,
        amap_line_id_min_request_interval_seconds=0,
        amap_rate_limit_retries=0,
        amap_rate_limit_backoff_seconds=0,
    )


def _service(
    transport: httpx.MockTransport | None,
    *,
    api_key: str | None = "test-amap-key",
    expected_endpoint: str = "lineid",
) -> tuple[OnDemandSyncService, _IngestionTracker, httpx.Client | None]:
    http_client = httpx.Client(transport=transport) if transport is not None else None
    service = OnDemandSyncService(
        _EmptyFactory(),  # type: ignore[arg-type]
        AmapClient(_settings(api_key=api_key), http_client),
    )
    tracker = _IngestionTracker(expected_endpoint)
    service.ingestion = tracker  # type: ignore[assignment]
    service._record_line_summary_reason = lambda *args, **kwargs: None  # type: ignore[method-assign]
    return service, tracker, http_client


def test_line_name_search_uses_linename_and_returns_imported_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "1", "count": "0", "buslines": []})

    service, _, client = _service(
        httpx.MockTransport(handler), expected_endpoint="linename"
    )
    line = BusLine(
        id=19,
        amap_line_id="310100024547",
        line_name="576路",
        amap_name="576路(曲阳路玉田路--芦恒路枢纽站)",
        city_code="021",
        polyline_raw="121.1,31.1;121.2,31.2",
    )
    results = iter([[], [line]])
    monkeypatch.setattr(
        TransitService,
        "search_lines",
        lambda self, query, city_code, limit: next(results),
    )
    try:
        items, run_id = service.search_lines(query="576路", city_code="021", limit=20)
    finally:
        assert client is not None
        client.close()

    assert items == [line]
    assert run_id == 901
    assert requests[0].url.path.endswith("/v3/bus/linename")
    assert requests[0].url.params["keywords"] == "576路"
    assert requests[0].url.params["city"] == "021"
    assert requests[0].url.params["extensions"] == "all"


def test_lineid_empty_result_becomes_not_found_after_amap() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"status": "1", "count": "0", "buslines": []}
        )
    )
    service, tracker, client = _service(transport)
    try:
        with pytest.raises(TransitNotFound) as error:
            service.backfill_line(amap_line_id="missing-line")
    finally:
        assert client is not None
        client.close()

    assert error.value.code == "NOT_FOUND_AFTER_AMAP"
    assert error.value.status_code == 404
    assert tracker.failed == []


@pytest.mark.parametrize(
    "api_key,transport",
    [
        (None, None),
        (
            "test-amap-key",
            httpx.MockTransport(
                lambda request: (_ for _ in ()).throw(
                    httpx.ConnectError("network unavailable", request=request)
                )
            ),
        ),
        (
            "test-amap-key",
            httpx.MockTransport(
                lambda request: (_ for _ in ()).throw(
                    httpx.ReadTimeout("upstream timeout", request=request)
                )
            ),
        ),
    ],
    ids=["missing-key", "network-failure", "timeout"],
)
def test_lineid_unavailable_failures_become_503(
    api_key: str | None, transport: httpx.MockTransport | None
) -> None:
    service, tracker, client = _service(transport, api_key=api_key)
    try:
        with pytest.raises(TransitUpstreamError) as error:
            service.backfill_line(amap_line_id="unavailable-line")
    finally:
        if client is not None:
            client.close()

    assert error.value.code == "AMAP_UNAVAILABLE"
    assert error.value.status_code == 503
    assert tracker.failed and tracker.failed[0][0] == 901


def test_lineid_business_error_becomes_502() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"},
        )
    )
    service, tracker, client = _service(transport)
    try:
        with pytest.raises(TransitUpstreamError) as error:
            service.backfill_line(amap_line_id="business-error-line")
    finally:
        assert client is not None
        client.close()

    assert error.value.code == "AMAP_BUSINESS_ERROR"
    assert error.value.status_code == 502
    assert tracker.failed and tracker.failed[0][0] == 901


def _table_counts(session: Session) -> tuple[int, int, int, int]:
    return (
        session.scalar(select(func.count()).select_from(BusStop)) or 0,
        session.scalar(select(func.count()).select_from(BusLine)) or 0,
        session.scalar(select(func.count()).select_from(BusLineStop)) or 0,
        session.scalar(select(func.count()).select_from(BusLinePathPoint)) or 0,
    )


@pytest.mark.mysql_live
def test_lineid_import_failure_rolls_back_business_rows_and_keeps_failed_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.getenv("TRANSIT_LIVE_ROLLBACK_TEST") != "1":
        pytest.skip("设置 TRANSIT_LIVE_ROLLBACK_TEST=1 后执行真实 MySQL 回滚验证")

    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    service = IngestionService(factory)
    keyword = "codex-stage6-lineid-rollback"
    run_id = service._create_run(
        endpoint="lineid",
        trigger_type="manual",
        request_keyword=keyword,
        city_code=None,
    )
    with factory() as session:
        counts_before = _table_counts(session)

    original_upsert_stop = service._upsert_stop
    stop_calls = 0

    def fail_after_first_stop(*args: Any, **kwargs: Any) -> Any:
        nonlocal stop_calls
        result = original_upsert_stop(*args, **kwargs)
        stop_calls += 1
        if stop_calls == 2:
            raise RuntimeError("forced stage6 lineid rollback")
        return result

    monkeypatch.setattr(service, "_upsert_stop", fail_after_first_stop)
    payload = {
        "status": "1",
        "buslines": [
            {
                "id": "codex-stage6-rollback-line",
                "name": "阶段六回滚测试线(起点--终点)",
                "citycode": "021",
                "polyline": "121.100000,31.100000;121.200000,31.200000",
                "busstops": [
                    {"id": "codex-stage6-stop-a", "name": "回滚测试站A", "location": "121.100000,31.100000", "sequence": "1"},
                    {"id": "codex-stage6-stop-b", "name": "回滚测试站B", "location": "121.200000,31.200000", "sequence": "2"},
                ],
            }
        ],
    }

    try:
        with pytest.raises(IngestionError, match="入库失败"):
            service.import_line_response(
                payload,
                trigger_type="manual",
                request_keyword=keyword,
                city_code=None,
                amap_line_ids={"codex-stage6-rollback-line"},
                ingestion_run_id=run_id,
            )

        with factory() as session:
            assert _table_counts(session) == counts_before
            assert session.scalar(
                select(BusLine).where(
                    BusLine.amap_line_id == "codex-stage6-rollback-line"
                )
            ) is None
            failed_run = session.get(IngestionRun, run_id)
            assert failed_run is not None
            assert failed_run.endpoint == "lineid"
            assert failed_run.status == "failed"
            assert failed_run.error_message is not None
            assert "forced stage6 lineid rollback" in failed_run.error_message
    finally:
        engine.dispose()
