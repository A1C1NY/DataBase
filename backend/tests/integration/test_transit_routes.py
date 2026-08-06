"""HTTP contracts for database-only reads and line-ID error mapping."""

from __future__ import annotations

from contextlib import AbstractContextManager
from decimal import Decimal
from typing import Self

import pytest
from fastapi import HTTPException

from app.api.routes import lines as line_routes
from app.api.routes import stops as stop_routes
from app.models.transit import BusStop
from app.services.on_demand_sync import TransitNotFound, TransitUpstreamError


class _Session(AbstractContextManager["_Session"]):
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _Factory:
    def __call__(self) -> _Session:
        return _Session()


def _stop() -> BusStop:
    stop = BusStop(
        id=37,
        amap_stop_id="BV10024705",
        stop_name="赤峰路密云路(公交站)",
        normalized_name="赤峰路密云路(公交站)",
        longitude=Decimal("121.4979010"),
        latitude=Decimal("31.2814030"),
        city_code="021",
        line_membership_status="partial",
        unresolved_line_summaries=[
            {
                "amap_line_id": "310100016007",
                "line_name": "576路",
                "amap_name": "576路(曲阳路玉田路--芦恒路枢纽站)",
                "start_stop_name": "曲阳路玉田路",
                "end_stop_name": "芦恒路枢纽站",
                "reason": None,
            }
        ],
    )
    stop.coordinate_system = "GCJ02"
    return stop


def test_stop_lines_is_database_only_and_makes_no_upstream_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_calls = 0

    def forbidden_sync() -> object:
        nonlocal sync_calls
        sync_calls += 1
        raise AssertionError("stop-lines must not construct an Amap client")

    monkeypatch.setattr(stop_routes, "get_session_factory", lambda: _Factory())
    monkeypatch.setattr(stop_routes, "_sync", forbidden_sync)
    monkeypatch.setattr(stop_routes.TransitService, "get_stop", lambda self, stop_id: _stop())
    monkeypatch.setattr(stop_routes.TransitService, "get_lines_for_stop", lambda self, stop_id: [])

    body = stop_routes.get_stop_lines(37).model_dump(mode="json")

    assert body["data_source"] == "database"
    assert body["partial"] is True
    assert body["lines"] == []
    assert body["unresolved_summaries"][0]["amap_line_id"] == "310100016007"
    assert sync_calls == 0


class _RaisingSync:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def backfill_line(self, *, amap_line_id: str) -> int:
        raise self.error


@pytest.mark.parametrize(
    "error,status_code,code",
    [
        (TransitNotFound("高德和本地数据库均未找到线路"), 404, "NOT_FOUND_AFTER_AMAP"),
        (TransitUpstreamError("AMAP_UNAVAILABLE", "高德不可用", status_code=503), 503, "AMAP_UNAVAILABLE"),
        (TransitUpstreamError("AMAP_BUSINESS_ERROR", "高德业务错误", status_code=502), 502, "AMAP_BUSINESS_ERROR"),
    ],
)
def test_line_by_amap_maps_service_errors_to_http_contract(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    monkeypatch.setattr(line_routes, "get_session_factory", lambda: _Factory())
    monkeypatch.setattr(
        line_routes.TransitService, "get_line_by_amap_id", lambda self, line_id: None
    )
    monkeypatch.setattr(line_routes, "_sync", lambda: _RaisingSync(error))

    with pytest.raises(HTTPException) as raised:
        line_routes.get_line_by_amap("not-in-database")

    assert raised.value.status_code == status_code
    assert raised.value.detail["code"] == code
