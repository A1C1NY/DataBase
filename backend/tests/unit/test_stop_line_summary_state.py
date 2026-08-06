from decimal import Decimal
from unittest.mock import MagicMock

from app.api.routes import stops as stop_routes
from app.models.transit import BusStop
from app.services.ingestion import IngestionService
from app.services.transit import TransitService


def _stop() -> BusStop:
    return BusStop(
        id=1,
        amap_stop_id="S1",
        stop_name="测试站",
        normalized_name="测试站",
        longitude=Decimal("121.0000000"),
        latitude=Decimal("31.0000000"),
        coordinate_system="GCJ02",
        city_code="021",
        line_membership_status="partial",
        unresolved_line_summaries=[
            {
                "amap_line_id": "L1",
                "line_name": "测试线",
                "amap_name": "测试线(A--B)",
                "start_stop_name": "A",
                "end_stop_name": "B",
                "reason": None,
            }
        ],
        is_active=True,
    )


def test_stored_summary_is_returned_without_upstream_access() -> None:
    unresolved = TransitService.get_unresolved_lines_for_stop(_stop())

    assert len(unresolved) == 1
    assert unresolved[0].amap_line_id == "L1"
    assert unresolved[0].reason is None


def test_confirming_clicked_line_removes_only_its_summary() -> None:
    stop = _stop()

    IngestionService._confirm_line_summary(stop, "L1")

    assert stop.unresolved_line_summaries is None
    assert stop.line_membership_status == "complete"


def test_stop_lines_route_is_database_only(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    session = MagicMock()
    session.scalar.return_value = _stop()
    session.scalars.return_value = []
    context = MagicMock()
    context.__enter__.return_value = session
    factory = MagicMock(return_value=context)
    monkeypatch.setattr(stop_routes, "get_session_factory", lambda: factory)

    response = stop_routes.get_stop_lines(1)

    assert response.data_source == "database"
    assert response.partial is True
    assert [item.amap_line_id for item in response.unresolved_summaries] == ["L1"]
