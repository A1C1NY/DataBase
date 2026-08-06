from datetime import time
from pathlib import Path

import pytest

from app.integrations.amap.parser import (
    AmapParseError,
    load_line_sample,
    parse_line_response,
)

ROOT = Path(__file__).resolve().parents[3]


def test_line_sample_parses_two_directions_and_full_geometry() -> None:
    lines = load_line_sample(ROOT / "bus_line_raw_gaode.json")

    assert len(lines) == 2
    assert {line.amap_line_id for line in lines} == {"310100015143", "310100015144"}
    assert all(line.line_name == "980路" for line in lines)
    assert all(len(line.stops) == 29 for line in lines)
    assert all(len(line.path_points) > 100 for line in lines)
    assert lines[0].first_departure_time == time(5, 30)
    assert lines[0].last_departure_time == time(22, 30)
    assert lines[0].distance_km is not None


def test_line_parser_turns_bad_optional_values_into_warnings() -> None:
    payload = {
        "status": "1",
        "buslines": [
            {
                "id": "L1",
                "name": "测试线(A--B)",
                "polyline": "121,31;121.1,31.1",
                "start_time": "2561",
                "loop": "unknown",
                "distance": "not-a-number",
                "busstops": [
                    {"id": "S1", "name": "A", "location": "121,31", "sequence": "1"},
                    {
                        "id": "S2",
                        "name": "B",
                        "location": "121.1,31.1",
                        "sequence": "2",
                    },
                ],
            }
        ],
    }

    line = parse_line_response(payload)[0]

    assert line.first_departure_time is None
    assert line.loop_flag is None
    assert line.distance_km is None
    assert len(line.warnings) == 3


def test_line_parser_normalizes_empty_company_array_to_none() -> None:
    payload = {
        "status": "1",
        "buslines": [
            {
                "id": "L1",
                "name": "测试线(A--B)",
                "company": [],
                "polyline": "121,31;121.1,31.1",
                "busstops": [
                    {"id": "S1", "name": "A", "location": "121,31", "sequence": "1"}
                ],
            }
        ],
    }

    line = parse_line_response(payload)[0]

    assert line.company_name is None


def test_line_parser_rejects_non_contiguous_stop_sequence() -> None:
    payload = {
        "status": "1",
        "buslines": [
            {
                "id": "L1",
                "name": "测试线(A--B)",
                "polyline": "121,31;121.1,31.1",
                "busstops": [
                    {"id": "S1", "name": "A", "location": "121,31", "sequence": "2"}
                ],
            }
        ],
    }

    with pytest.raises(AmapParseError, match="站序必须从 1 连续"):
        parse_line_response(payload)


def test_line_parser_rejects_mismatched_reverse_direction() -> None:
    def line(line_id: str, reverse_id: str) -> dict[str, object]:
        return {
            "id": line_id,
            "direc": reverse_id,
            "name": f"测试线({line_id})",
            "polyline": "121,31;121.1,31.1",
            "busstops": [
                {"id": "S1", "name": "A", "location": "121,31", "sequence": "1"}
            ],
        }

    with pytest.raises(AmapParseError, match="direc 未互指"):
        parse_line_response(
            {"status": "1", "buslines": [line("L1", "L2"), line("L2", "L3")]}
        )
