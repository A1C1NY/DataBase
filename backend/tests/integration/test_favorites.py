"""Stop and line favorite route behavior without a live database."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from unittest.mock import Mock

from app.api.routes.favorites import (
    add_favorite_line,
    add_favorite_stop,
    list_favorite_lines,
    list_favorite_stops,
    remove_favorite_line,
    remove_favorite_stop,
)
from app.models.account import FavoriteLine, FavoriteStop, User
from app.models.transit import BusLine, BusStop


def _user(user_id: int = 5) -> User:
    return User(
        id=user_id,
        username=f"passenger-{user_id}",
        password_hash="argon-hash",
        role="passenger",
        is_active=True,
    )


def _stop() -> BusStop:
    stop = BusStop(
        id=37,
        amap_stop_id="BV10024705",
        stop_name="赤峰路密云路(公交站)",
        normalized_name="赤峰路密云路(公交站)",
        longitude=Decimal("121.4979010"),
        latitude=Decimal("31.2814030"),
        city_code="021",
        is_active=True,
    )
    stop.coordinate_system = "GCJ02"
    return stop


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


def test_stop_and_line_put_are_idempotent() -> None:
    user = _user()
    stop_session = Mock()
    stop_session.get.side_effect = [_stop(), None]
    line_session = Mock()
    line_session.get.side_effect = [_line(), FavoriteLine(user_id=5, line_id=19)]

    assert add_favorite_stop(37, stop_session, user).status_code == 204
    assert add_favorite_line(19, line_session, user).status_code == 204

    stop_session.add.assert_called_once()
    stop_session.commit.assert_called_once()
    line_session.add.assert_not_called()
    line_session.commit.assert_not_called()


def test_repeated_delete_always_returns_204() -> None:
    session = Mock()
    user = _user()

    assert remove_favorite_stop(37, session, user).status_code == 204
    assert remove_favorite_line(19, session, user).status_code == 204

    assert session.execute.call_count == 2
    assert session.commit.call_count == 2


def test_favorite_lists_include_objects_and_created_at() -> None:
    created_at = datetime(2026, 8, 9, 12, 30)  # noqa: DTZ001 - MySQL DATETIME is naive
    favorite_stop = FavoriteStop(user_id=5, stop_id=37, created_at=created_at)
    favorite_line = FavoriteLine(user_id=5, line_id=19, created_at=created_at)
    stop_session: Any = Mock()
    stop_session.scalar.return_value = 1
    stop_session.execute.return_value.all.return_value = [(favorite_stop, _stop())]
    line_session: Any = Mock()
    line_session.scalar.return_value = 1
    line_session.execute.return_value.all.return_value = [(favorite_line, _line())]

    stops = list_favorite_stops(stop_session, _user(), page=1, page_size=20)
    lines = list_favorite_lines(line_session, _user(), page=1, page_size=20)

    assert stops.total == 1
    assert stops.items[0].stop.id == 37
    assert stops.items[0].created_at == created_at
    assert lines.total == 1
    assert lines.items[0].line.id == 19
    assert lines.items[0].created_at == created_at
