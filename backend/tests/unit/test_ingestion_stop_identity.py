from decimal import Decimal
from unittest.mock import MagicMock

from app.integrations.amap.parser import ParsedLineStop, ParsedLineSummary, ParsedStop
from app.models.transit import BusStop
from app.services.ingestion import IngestionService


def test_line_import_does_not_overwrite_existing_canonical_stop() -> None:
    existing = BusStop(
        id=37,
        amap_stop_id="BV10024705",
        stop_name="赤峰路密云路(公交站)",
        normalized_name="赤峰路密云路(公交站)",
        longitude=Decimal("121.4979010"),
        latitude=Decimal("31.2814030"),
        city_code="021",
        line_membership_status="partial",
        last_ingestion_run_id=49,
        is_active=True,
    )
    line_stop = ParsedLineStop(
        amap_stop_id="BV10024705",
        stop_name="赤峰路密云路",
        normalized_name="赤峰路密云路",
        longitude=Decimal("121.4995650"),
        latitude=Decimal("31.2807570"),
        sequence_no=10,
    )
    session = MagicMock()
    session.scalar.return_value = existing

    returned, inserted = IngestionService(MagicMock())._upsert_stop(
        session,
        line_stop,
        ingestion_run_id=50,
        fallback_city_code="021",
    )

    assert returned is existing
    assert inserted is False
    assert existing.stop_name == "赤峰路密云路(公交站)"
    assert existing.longitude == Decimal("121.4979010")
    assert existing.latitude == Decimal("31.2814030")
    assert existing.last_ingestion_run_id == 49


def test_stop_import_persists_unresolved_line_summaries() -> None:
    existing = BusStop(
        id=37,
        amap_stop_id="BV10024705",
        stop_name="赤峰路密云路(公交站)",
        normalized_name="赤峰路密云路(公交站)",
        longitude=Decimal("121.4979010"),
        latitude=Decimal("31.2814030"),
        city_code="021",
        line_membership_status="unknown",
        is_active=True,
    )
    parsed = ParsedStop(
        amap_stop_id="BV10024705",
        stop_name="赤峰路密云路(公交站)",
        normalized_name="赤峰路密云路(公交站)",
        longitude=Decimal("121.4979010"),
        latitude=Decimal("31.2814030"),
        city_code="021",
        adcode="310110",
        line_summaries=(
            ParsedLineSummary(
                amap_line_id="L1",
                amap_name="测试线(A--B)",
                line_name="测试线",
                start_stop_name="A",
                end_stop_name="B",
            ),
        ),
    )
    session = MagicMock()
    session.scalar.return_value = existing
    session.scalars.return_value = []

    IngestionService(MagicMock())._upsert_stop(
        session,
        parsed,
        ingestion_run_id=70,
        fallback_city_code="021",
    )

    assert existing.line_membership_status == "partial"
    assert existing.unresolved_line_summaries == [
        {
            "amap_line_id": "L1",
            "line_name": "测试线",
            "amap_name": "测试线(A--B)",
            "start_stop_name": "A",
            "end_stop_name": "B",
            "reason": None,
        }
    ]
