"""Line-name search and line completeness behavior."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Self

from app.models.transit import BusLine
from app.services.on_demand_sync import OnDemandSyncService
from app.services.transit import TransitService


def _line() -> BusLine:
    return BusLine(
        id=19,
        amap_line_id="310100024547",
        line_name="576路",
        amap_name="576路(曲阳路玉田路--芦恒路枢纽站)",
        city_code="021",
        polyline_raw="121.1,31.1;121.2,31.2",
        is_active=True,
    )


class _Session(AbstractContextManager["_Session"]):
    def __init__(self, scalar_values: list[object]) -> None:
        self.scalar_values = scalar_values

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def scalar(self, statement: object) -> object:
        return self.scalar_values.pop(0)


class _Factory:
    def __init__(self, sessions: list[_Session]) -> None:
        self.sessions = sessions

    def __call__(self) -> _Session:
        return self.sessions.pop(0)


class _ForbiddenAmap:
    def query_line_by_id(self, *, amap_line_id: str) -> object:
        raise AssertionError("complete local line must not call Amap")


def test_line_is_complete_with_stops_and_path_points() -> None:
    session = _Session([3, 20])

    assert TransitService(session).is_line_complete(_line()) is True  # type: ignore[arg-type]


def test_line_is_incomplete_without_stops() -> None:
    session = _Session([0, 20])

    assert TransitService(session).is_line_complete(_line()) is False  # type: ignore[arg-type]


def test_complete_line_id_lookup_stays_database_only() -> None:
    service = OnDemandSyncService(
        _Factory([_Session([_line(), 3, 20])]),  # type: ignore[arg-type]
        _ForbiddenAmap(),  # type: ignore[arg-type]
    )

    assert service.backfill_line(amap_line_id="310100024547") == 0
