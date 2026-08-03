import json
from datetime import time
from decimal import Decimal
from pathlib import Path

import pytest

from app.integrations.amap.parser import (
    AmapParseError,
    parse_amap_line_response,
    parse_amap_stop_response,
)

ROOT = Path(__file__).resolve().parents[3]


def read_sample(name: str) -> dict[str, object]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_parses_two_amap_line_directions_and_ordered_routes() -> None:
    result = parse_amap_line_response(read_sample("bus_line_raw_gaode.json"))

    assert len(result) == 2
    assert [line.direction for line in result] == [0, 1]
    assert [line.amap_line_id for line in result] == ["310100015144", "310100015143"]
    assert all(line.line_name == "980路" for line in result)
    assert result[0].first_departure_time == time(5, 30)
    assert result[0].last_departure_time == time(22, 30)
    assert [stop.sequence_no for stop in result[0].stops] == list(
        range(1, len(result[0].stops) + 1)
    )
    assert result[0].stops[0].longitude == Decimal("121.51133")
    assert result[0].stops[0].latitude == Decimal("31.154711")


def test_parses_amap_stop_sample_without_merging_nearby_names() -> None:
    result = parse_amap_stop_response(read_sample("bus_stop_by_name.json"))

    assert len(result) == 2
    assert result[0].amap_stop_id == "BV10030918"
    assert result[1].amap_stop_id == "BV09279697"
    assert result[0].longitude != result[1].longitude
    assert "310100015144" in result[0].line_ids
    assert result[1].line_ids == ("310100015143",)


def test_external_numeric_ids_are_normalized_to_strings() -> None:
    payload = read_sample("bus_stop_by_name.json")
    payload["busstops"][0]["id"] = 123  # type: ignore[index]

    result = parse_amap_stop_response(payload)

    assert result[0].amap_stop_id == "123"


def test_rejects_non_reciprocal_line_directions() -> None:
    payload = read_sample("bus_line_raw_gaode.json")
    payload["buslines"][0]["direc"] = "wrong"  # type: ignore[index]

    with pytest.raises(AmapParseError, match="direc"):
        parse_amap_line_response(payload)
