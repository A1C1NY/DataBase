"""Normalize Shanghai nearby-transit data without database side effects."""

import re
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.time import build_planned_departure_at
from app.integrations.shanghai.schemas import ShanghaiNearbyResponse


class ShanghaiParseError(ValueError):
    pass


class ParsedShanghaiStop(BaseModel):
    model_config = ConfigDict(frozen=True)

    stop_id: str | None
    stop_name: str
    longitude: Decimal
    latitude: Decimal


class ParsedShanghaiLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    line_id: str
    direction: int
    line_name: str
    line_type: int | None
    start_stop_name: str | None
    end_stop_name: str | None
    first_departure_time: time | None
    last_departure_time: time | None

    @property
    def key(self) -> tuple[str, int]:
        return self.line_id, self.direction


class ParsedArrival(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_up_down: int | None = None
    current_bus_distance_m: int | None = None
    current_bus_arrival_min: int | None = None
    current_bus_comfort: int | None = None
    current_bus_stop_count: int | None = None
    current_license_plate: str | None = None
    current_barrier_free: bool | None = None
    next_bus_distance_m: int | None = None
    next_bus_arrival_min: int | None = None
    next_bus_stop_count: int | None = None
    next_license_plate: str | None = None
    next_barrier_free: bool | None = None


class ParsedDispatchCar(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence_no: int
    vehicle_text: str | None = None
    is_barrier_free: bool | None = None
    planned_departure_at: datetime | None = None
    countdown_text: str | None = None
    countdown_seconds: int | None = None


class ParsedDispatchSchedule(BaseModel):
    model_config = ConfigDict(frozen=True)

    line_key: tuple[str, int]
    schedule_code: int | None = None
    message_default: str | None = None
    message_short: str | None = None
    cars: tuple[ParsedDispatchCar, ...] = ()


class ParsedShanghaiEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    line: ParsedShanghaiLine
    stop: ParsedShanghaiStop
    arrival: ParsedArrival | None = None


class ParsedShanghaiResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    entries: tuple[ParsedShanghaiEntry, ...]
    schedules: tuple[ParsedDispatchSchedule, ...]
    issues: tuple[str, ...] = ()


def _optional_int(value: object, field: str, issues: list[str]) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        issues.append(f"{field} 不是有效整数: {value!r}")
        return None
    if parsed < 0:
        issues.append(f"{field} 不能为负数: {value!r}")
        return None
    return parsed


def _direction(value: object, field: str) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ShanghaiParseError(f"{field} 缺少有效方向") from exc
    if parsed not in (0, 1):
        raise ShanghaiParseError(f"{field} 方向只能是 0 或 1")
    return parsed


def _optional_bool(value: object, vehicle: str | None = None) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True"):
        return True
    if value in (0, "0", "false", "False"):
        return False
    if vehicle:
        return "无障碍" in vehicle
    return None


def _point(lon: object, lat: object, context: str) -> tuple[Decimal, Decimal]:
    try:
        longitude, latitude = Decimal(str(lon)), Decimal(str(lat))
    except (InvalidOperation, ValueError) as exc:
        raise ShanghaiParseError(f"{context} 缺少有效坐标") from exc
    if not Decimal("-180") <= longitude <= Decimal("180"):
        raise ShanghaiParseError(f"{context} 经度越界")
    if not Decimal("-90") <= latitude <= Decimal("90"):
        raise ShanghaiParseError(f"{context} 纬度越界")
    return longitude, latitude


def _clock(value: str | None, issues: list[str], field: str) -> time | None:
    if not value:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        issues.append(f"{field} 不是有效时间: {value!r}")
        return None


def _countdown_seconds(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(?:剩余)?\s*(\d+)\s*分钟", value)
    if match:
        return int(match.group(1)) * 60
    if "即将发车" in value:
        return 0
    return None


def parse_shanghai_response(
    data: ShanghaiNearbyResponse | dict[str, Any], collected_at: datetime
) -> ParsedShanghaiResponse:
    if collected_at.tzinfo is None:
        raise ValueError("collected_at 必须是带时区的 datetime")
    response = data if isinstance(data, ShanghaiNearbyResponse) else (
        ShanghaiNearbyResponse.model_validate(data)
    )
    if response.retCode not in (None, 0, "0"):
        raise ShanghaiParseError(f"上海接口返回业务错误 retCode={response.retCode!r}")

    entries: list[ParsedShanghaiEntry] = []
    schedules: dict[tuple[str, int], ParsedDispatchSchedule] = {}
    issues: list[str] = []
    for index, item in enumerate(response.nearByTrafficLineStop, start=1):
        context = f"第 {index} 条上海记录"
        if not item.lineId or not item.lineName or not item.stopName or item.point is None:
            raise ShanghaiParseError(f"{context} 缺少线路、站点或坐标")
        direction = _direction(item.upDown, context)
        longitude, latitude = _point(item.point.lon, item.point.lat, context)
        line = ParsedShanghaiLine(
            line_id=item.lineId,
            direction=direction,
            line_name=item.lineName,
            line_type=_optional_int(item.type, f"{context}.type", issues),
            start_stop_name=item.startStopName,
            end_stop_name=item.endStopName,
            first_departure_time=_clock(
                item.startEarlyLateTime, issues, f"{context}.startEarlyLateTime"
            ),
            last_departure_time=_clock(
                item.endEarlyLateTime, issues, f"{context}.endEarlyLateTime"
            ),
        )
        stop = ParsedShanghaiStop(
            stop_id=item.stopId,
            stop_name=item.stopName,
            longitude=longitude,
            latitude=latitude,
        )

        arrival = None
        if item.sai is not None:
            sai = item.sai
            arrival = ParsedArrival(
                source_up_down=(
                    _direction(sai.upDown, f"{context}.sai") if sai.upDown is not None else None
                ),
                current_bus_distance_m=_optional_int(
                    sai.currentBusDistance, f"{context}.currentBusDistance", issues
                ),
                current_bus_arrival_min=_optional_int(
                    sai.currentBusArriveTime, f"{context}.currentBusArriveTime", issues
                ),
                current_bus_comfort=_optional_int(
                    sai.currentBusComfort, f"{context}.currentBusComfort", issues
                ),
                current_bus_stop_count=_optional_int(
                    sai.currentBusStopCount, f"{context}.currentBusStopCount", issues
                ),
                current_license_plate=sai.currentLicensePlate,
                current_barrier_free=_optional_bool(
                    sai.currentBarrierFree, sai.currentLicensePlate
                ),
                next_bus_distance_m=_optional_int(
                    sai.nextBusDistance, f"{context}.nextBusDistance", issues
                ),
                next_bus_arrival_min=_optional_int(
                    sai.nextBusArriveTime, f"{context}.nextBusArriveTime", issues
                ),
                next_bus_stop_count=_optional_int(
                    sai.nextBusStopCount, f"{context}.nextBusStopCount", issues
                ),
                next_license_plate=sai.nextLicensePlate,
                next_barrier_free=_optional_bool(sai.nextBarrierFree, sai.nextLicensePlate),
            )

        entries.append(ParsedShanghaiEntry(line=line, stop=stop, arrival=arrival))

        schedule = item.dispatchCarSchedule
        if schedule is not None and line.key not in schedules:
            cars: list[ParsedDispatchCar] = []
            for sequence, car in enumerate(schedule.dispatchCars, start=1):
                planned_at = build_planned_departure_at(car.time, collected_at)
                if car.time and planned_at is None:
                    issues.append(f"{context}.dispatchCars[{sequence}] 无法可靠确定计划日期")
                cars.append(
                    ParsedDispatchCar(
                        sequence_no=sequence,
                        vehicle_text=car.vehicle,
                        is_barrier_free=_optional_bool(None, car.vehicle),
                        planned_departure_at=planned_at,
                        countdown_text=car.countdown,
                        countdown_seconds=_countdown_seconds(car.countdown),
                    )
                )
            schedules[line.key] = ParsedDispatchSchedule(
                line_key=line.key,
                schedule_code=_optional_int(
                    schedule.scheduleCode, f"{context}.scheduleCode", issues
                )
                if schedule.scheduleCode not in (-1, "-1")
                else -1,
                message_default=schedule.scheduleMsgDefault,
                message_short=schedule.scheduleMsgShort,
                cars=tuple(cars),
            )
    return ParsedShanghaiResponse(
        entries=tuple(entries), schedules=tuple(schedules.values()), issues=tuple(issues)
    )


def load_shanghai_response(path: str | Path, collected_at: datetime) -> ParsedShanghaiResponse:
    dto = ShanghaiNearbyResponse.model_validate_json(Path(path).read_text())
    return parse_shanghai_response(dto, collected_at)


parse_response = parse_shanghai_response
