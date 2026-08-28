from pathlib import Path

import pytest

from app.integrations.amap.parser import (
    AmapParseError,
    load_stop_sample,
    parse_stop_response,
)

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("filename", ["bus_stop_by_name.json", "bus_stop_raw_gaode.json"])
def test_stop_samples_parse_all_candidates(filename: str) -> None:
    stops = load_stop_sample(ROOT / filename)

    assert len(stops) == 2
    assert {stop.amap_stop_id for stop in stops} == {"BV10030918", "BV09279697"}
    assert all(stop.city_code == "021" for stop in stops)
    assert all(stop.longitude > 120 for stop in stops)


def test_stop_sample_keeps_line_summaries_and_empty_names_as_none() -> None:
    stops = load_stop_sample(ROOT / "bus_stop_by_name.json")
    main_stop = next(stop for stop in stops if stop.amap_stop_id == "BV10030918")
    summary = next(
        item for item in main_stop.line_summaries if item.amap_line_id == "310100015143"
    )

    assert len(main_stop.line_summaries) == 8
    assert summary.line_name == "980路"
    assert summary.start_stop_name is None
    assert summary.end_stop_name is None


def test_stop_parser_rejects_invalid_coordinate() -> None:
    payload = {
        "status": "1",
        "busstops": [{"id": "S1", "name": "测试站", "location": "999,31"}],
    }

    with pytest.raises(AmapParseError, match="经度越界"):
        parse_stop_response(payload)


def test_stop_parser_rejects_business_error() -> None:
    with pytest.raises(AmapParseError, match="10001"):
        parse_stop_response({"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"})

