"""Stop detail view event behavior and HTTP input contract."""

from decimal import Decimal
from unittest.mock import Mock

import pytest

from app.models.account import StopViewEvent, User
from app.models.transit import BusStop
from app.schemas.events import StopViewEntryPoint
from app.services.view_events import StopViewEventService


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


def test_successful_anonymous_detail_adds_exactly_one_event() -> None:
    session = Mock()
    service = StopViewEventService(session)
    stop = _stop()
    session.scalar.return_value = stop

    assert service.open_stop_detail(
        37, entry_point=StopViewEntryPoint.SEARCH, user=None
    ) is stop

    session.add.assert_called_once()
    event = session.add.call_args.args[0]
    assert isinstance(event, StopViewEvent)
    assert event.stop_id == 37
    assert event.entry_point == "search"
    assert event.actor_role == "anonymous"
    assert event.user_id is None
    session.commit.assert_called_once()


def test_line_map_detail_snapshots_authenticated_role() -> None:
    session = Mock()
    session.scalar.return_value = _stop()
    user = User(id=9, username="analyst9", password_hash="hash", role="analyst")

    StopViewEventService(session).open_stop_detail(
        37, entry_point=StopViewEntryPoint.LINE_MAP, user=user
    )

    event = session.add.call_args.args[0]
    assert event.entry_point == "line_map"
    assert event.actor_role == "analyst"
    assert event.user_id == 9


def test_missing_detail_adds_no_event() -> None:
    session = Mock()
    session.scalar.return_value = None

    result = StopViewEventService(session).open_stop_detail(
        404, entry_point=StopViewEntryPoint.DIRECT, user=None
    )

    assert result is None
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_event_write_failure_is_rolled_back() -> None:
    session = Mock()
    session.scalar.return_value = _stop()
    session.commit.side_effect = RuntimeError("database unavailable")

    try:
        StopViewEventService(session).open_stop_detail(
            37, entry_point=StopViewEntryPoint.FAVORITE, user=None
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("write failure must propagate")

    session.rollback.assert_called_once()


def test_detail_endpoint_rejects_unknown_entry_point() -> None:
    with pytest.raises(ValueError):
        StopViewEntryPoint("map_move")
