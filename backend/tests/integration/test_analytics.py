"""Fixed-data analytics calculations and API contract tests."""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.api.dependencies import require_roles
from app.api.routes.analytics import _bbox
from app.core.time import SHANGHAI_TZ
from app.geo.grid import parse_bbox
from app.models.transit import BusStop
from app.services.analytics import (
    AnalyticsService,
    _distribution_items,
    normalize_range,
)


def _local(day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(2026, 8, day, hour, minute, tzinfo=SHANGHAI_TZ).replace(tzinfo=None)


class _RowsSession:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows
        self.statement: object | None = None

    def execute(self, statement: object) -> list[tuple[object, ...]]:
        self.statement = statement
        return self.rows


def test_stop_heatmap_counts_distinct_stops_per_grid() -> None:
    session = _RowsSession(
        [
            (1, Decimal("121.5000000"), Decimal("31.2000000")),
            (2, Decimal("121.5001000"), Decimal("31.2001000")),
            (2, Decimal("121.5001000"), Decimal("31.2001000")),
        ]
    )

    response = AnalyticsService(session).stop_heatmap(  # type: ignore[arg-type]
        parse_bbox("121.49,31.19,121.51,31.21"), 300
    )

    assert response.data_source == "database"
    assert len(response.geojson["features"]) == 1
    assert response.geojson["features"][0]["properties"] == {
        "metric": "stop_density",
        "weight": 2,
        "grid_size_m": 300,
    }
    assert response.geojson["metadata"]["coordinate_system"] == "WGS84"


def test_line_heatmap_deduplicates_each_direction_per_grid() -> None:
    session = _RowsSession(
        [
            (10, 1, Decimal("121.5000000"), Decimal("31.2000000")),
            (10, 2, Decimal("121.5005000"), Decimal("31.2000000")),
            (11, 1, Decimal("121.5001000"), Decimal("31.2001000")),
            (11, 2, Decimal("121.5006000"), Decimal("31.2001000")),
        ]
    )

    response = AnalyticsService(session).line_heatmap(  # type: ignore[arg-type]
        parse_bbox("121.49,31.19,121.51,31.21"), 2000
    )

    assert len(response.geojson["features"]) == 1
    assert response.geojson["features"][0]["properties"]["weight"] == 2
    assert response.geojson["features"][0]["properties"]["metric"] == "line_density"


def test_hour_distribution_always_returns_24_zero_filled_buckets() -> None:
    items = _distribution_items(
        [_local(10, 8), _local(10, 8, 30)],
        _local(10),
        _local(11),
        "hour",
    )

    assert len(items) == 24
    assert items[8].detail_view_count == 2
    assert sum(item.detail_view_count for item in items) == 2


def test_day_and_weekday_hour_distributions_are_zero_filled() -> None:
    day_items = _distribution_items(
        [_local(11, 9)],
        _local(10),
        _local(13),
        "day",
    )
    weekday_items = _distribution_items(
        [_local(11, 9)],
        _local(10),
        _local(13),
        "weekday_hour",
    )

    assert [item.detail_view_count for item in day_items] == [0, 1, 0]
    assert len(weekday_items) == 168
    assert sum(item.detail_view_count for item in weekday_items) == 1


def test_time_range_uses_shanghai_and_left_closed_right_open_sql() -> None:
    start, end = normalize_range(_local(10), _local(11))

    assert start == _local(10)
    assert end == _local(11)

    session = _RowsSession([(3, "赤峰路密云路", 4, 2)])
    response = AnalyticsService(session).stop_popularity(  # type: ignore[arg-type]
        _local(10), _local(11), 10
    )
    sql = str(session.statement)
    assert "stop_view_events.viewed_at >=" in sql
    assert "stop_view_events.viewed_at <" in sql
    assert response.metric_name == "站点详情访问次数"
    assert response.items[0].detail_view_count == 4
    assert response.items[0].unique_user_count == 2


def test_distribution_filters_passengers_by_default() -> None:
    stop = BusStop(
        id=7,
        stop_name="测试站",
        normalized_name="测试站",
        longitude=Decimal("121.5"),
        latitude=Decimal("31.2"),
        is_active=True,
    )
    session = Mock()
    session.scalar.return_value = stop
    session.scalars.return_value = [_local(11, 9)]

    response = AnalyticsService(session).stop_view_distribution(
        7, _local(11), _local(12), "hour", "passenger"
    )

    assert response is not None
    assert response.items[9].detail_view_count == 1
    statement = str(session.scalars.call_args.args[0])
    assert "stop_view_events.actor_role" in statement


def test_analytics_permission_and_bbox_error_contracts() -> None:
    analyst = SimpleNamespace(role="analyst")
    admin = SimpleNamespace(role="admin")
    passenger = SimpleNamespace(role="passenger")
    dependency = require_roles("analyst", "admin")

    assert dependency(analyst).role == "analyst"
    assert dependency(admin).role == "admin"
    with pytest.raises(HTTPException) as forbidden:
        dependency(passenger)
    assert forbidden.value.status_code == 403
    with pytest.raises(HTTPException) as invalid_bbox:
        _bbox("122,32,121,31")
    assert invalid_bbox.value.status_code == 422
    assert invalid_bbox.value.detail["code"] == "INVALID_BBOX"
