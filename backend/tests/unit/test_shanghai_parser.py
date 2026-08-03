import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from app.core.time import SHANGHAI_TZ
from app.integrations.shanghai.parser import parse_shanghai_response

ROOT = Path(__file__).resolve().parents[3]


def read_sample() -> dict[str, object]:
    return json.loads((ROOT / "raw_result.json").read_text(encoding="utf-8"))


def one_item(index: int = 0) -> dict[str, object]:
    payload = read_sample()
    item = deepcopy(payload["nearByTrafficLineStop"][index])  # type: ignore[index]
    return {"nearByTrafficLineStop": [item], "retCode": 0}


def test_parses_real_response_and_uses_line_id_plus_direction() -> None:
    result = parse_shanghai_response(
        read_sample(), datetime(2026, 8, 3, 17, 40, tzinfo=SHANGHAI_TZ)
    )

    keys = {entry.line.key for entry in result.entries}
    assert ("10469", 1) in keys
    assert ("10469", 0) in keys
    first = result.entries[0]
    assert first.stop.stop_id == "129679"
    assert first.arrival is not None
    assert first.arrival.current_bus_distance_m == 548
    assert first.arrival.next_bus_arrival_min == 9
    assert first.arrival.current_barrier_free is True


def test_missing_sai_and_dispatch_cars_remain_empty() -> None:
    payload = one_item(1)  # 338 路样例没有 sai，也没有 dispatchCars。

    result = parse_shanghai_response(
        payload, datetime(2026, 8, 3, 23, 50, tzinfo=SHANGHAI_TZ)
    )

    assert result.entries[0].arrival is None
    assert result.schedules[0].cars == ()
    assert result.schedules[0].schedule_code == -1


def test_single_vehicle_keeps_second_vehicle_missing() -> None:
    payload = one_item()
    item = payload["nearByTrafficLineStop"][0]  # type: ignore[index]
    item["dispatchCarSchedule"]["dispatchCars"] = item["dispatchCarSchedule"]["dispatchCars"][:1]  # type: ignore[index]
    sai = item["sai"]  # type: ignore[index]
    for key in (
        "nextBusDistance",
        "nextBusStopCount",
        "nextBusArriveTime",
        "nextLicensePlate",
        "nextBarrierFree",
    ):
        sai.pop(key, None)

    result = parse_shanghai_response(
        payload, datetime(2026, 8, 3, 17, 40, tzinfo=SHANGHAI_TZ)
    )

    arrival = result.entries[0].arrival
    assert arrival is not None
    assert arrival.next_bus_distance_m is None
    assert arrival.next_license_plate is None
    assert len(result.schedules[0].cars) == 1


def test_two_vehicles_string_numbers_and_accessibility_suffix() -> None:
    payload = one_item()
    item = payload["nearByTrafficLineStop"][0]  # type: ignore[index]
    item["dispatchCarSchedule"]["dispatchCars"] = item["dispatchCarSchedule"]["dispatchCars"][:2]  # type: ignore[index]
    item["sai"].pop("currentBarrierFree")  # type: ignore[index]

    result = parse_shanghai_response(
        payload, datetime(2026, 8, 3, 17, 40, tzinfo=SHANGHAI_TZ)
    )

    arrival = result.entries[0].arrival
    assert arrival is not None and arrival.current_barrier_free is True
    assert arrival.current_bus_stop_count == 1
    assert len(result.schedules[0].cars) == 2
    assert result.schedules[0].cars[1].countdown_seconds == 12 * 60
    assert result.schedules[0].cars[0].is_barrier_free is True


def test_dispatch_time_crosses_midnight() -> None:
    payload = one_item()
    car = payload["nearByTrafficLineStop"][0]["dispatchCarSchedule"]["dispatchCars"][0]  # type: ignore[index]
    car["time"] = "00:10"
    car["countdown"] = "剩余20分钟"

    result = parse_shanghai_response(
        payload, datetime(2026, 8, 3, 23, 50, tzinfo=SHANGHAI_TZ)
    )

    planned = result.schedules[0].cars[0].planned_departure_at
    assert planned == datetime(2026, 8, 4, 0, 10, tzinfo=SHANGHAI_TZ)


def test_duplicate_line_direction_schedule_is_deduplicated() -> None:
    payload = one_item()
    duplicate = deepcopy(payload["nearByTrafficLineStop"][0])  # type: ignore[index]
    duplicate["stopId"] = "another-stop"
    payload["nearByTrafficLineStop"].append(duplicate)  # type: ignore[union-attr]

    result = parse_shanghai_response(
        payload, datetime(2026, 8, 3, 17, 40, tzinfo=SHANGHAI_TZ)
    )

    assert len(result.entries) == 2
    assert len(result.schedules) == 1
