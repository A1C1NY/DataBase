from datetime import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.integrations.amap.schemas import AmapLineResponse, AmapStopResponse


class AmapParseError(ValueError):
    pass


class ParsedAmapStop(BaseModel):
    model_config = ConfigDict(frozen=True)

    amap_stop_id: str | None
    stop_name: str
    longitude: Decimal
    latitude: Decimal
    line_ids: tuple[str, ...] = ()
    sequence_no: int | None = None


class ParsedAmapLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    amap_line_id: str
    line_name: str
    direction: int
    start_stop_name: str
    end_stop_name: str
    first_departure_time: time | None
    last_departure_time: time | None
    stops: tuple[ParsedAmapStop, ...]


def _coordinates(location: str | None, context: str) -> tuple[Decimal, Decimal]:
    if not location:
        raise AmapParseError(f"{context} 缺少坐标")
    parts = location.split(",")
    if len(parts) != 2:
        raise AmapParseError(f"{context} 坐标格式错误: {location!r}")
    try:
        longitude, latitude = (Decimal(part.strip()) for part in parts)
    except InvalidOperation as exc:
        raise AmapParseError(f"{context} 坐标格式错误: {location!r}") from exc
    if not Decimal("-180") <= longitude <= Decimal("180"):
        raise AmapParseError(f"{context} 经度越界")
    if not Decimal("-90") <= latitude <= Decimal("90"):
        raise AmapParseError(f"{context} 纬度越界")
    return longitude, latitude


def _hhmm(value: str | None, context: str) -> time | None:
    if value is None or value == "":
        return None
    digits = str(value).strip().replace(":", "")
    if len(digits) != 4 or not digits.isdigit():
        raise AmapParseError(f"{context} 时间格式错误: {value!r}")
    hour, minute = int(digits[:2]), int(digits[2:])
    if hour > 23 or minute > 59:
        raise AmapParseError(f"{context} 时间格式错误: {value!r}")
    return time(hour, minute)


def _line_name(name: str | None) -> str:
    if not name or not name.strip():
        raise AmapParseError("线路缺少名称")
    return name.split("(", 1)[0].strip()


def parse_amap_stop_response(data: AmapStopResponse | dict[str, Any]) -> list[ParsedAmapStop]:
    response = data if isinstance(data, AmapStopResponse) else AmapStopResponse.model_validate(data)
    parsed: list[ParsedAmapStop] = []
    for index, stop in enumerate(response.busstops, start=1):
        if not stop.name:
            raise AmapParseError(f"第 {index} 个站点缺少名称")
        longitude, latitude = _coordinates(stop.location, f"站点 {stop.name}")
        parsed.append(
            ParsedAmapStop(
                amap_stop_id=stop.id,
                stop_name=stop.name,
                longitude=longitude,
                latitude=latitude,
                line_ids=tuple(line.id for line in stop.buslines if line.id is not None),
            )
        )
    return parsed


def parse_amap_line_response(data: AmapLineResponse | dict[str, Any]) -> list[ParsedAmapLine]:
    response = data if isinstance(data, AmapLineResponse) else AmapLineResponse.model_validate(data)
    if not response.buslines:
        return []


    if len(response.buslines) == 2:
        first, second = response.buslines
        if first.direc and first.direc != second.id or second.direc and second.direc != first.id:
            raise AmapParseError("高德线路的两个方向没有通过 direc 互相对应")
    elif len(response.buslines) > 2:
        raise AmapParseError("一次线路响应只能包含同一线路的两个方向")

    result: list[ParsedAmapLine] = []
    for direction, line in enumerate(response.buslines):
        if line.id is None or not line.start_stop or not line.end_stop:
            raise AmapParseError(f"第 {direction + 1} 个线路方向缺少 ID 或起终点")
        if not line.busstops:
            raise AmapParseError(f"线路 {line.id} 缺少完整站序")

        stops: list[ParsedAmapStop] = []
        seen_sequences: set[int] = set()
        for expected, stop in enumerate(line.busstops, start=1):
            if not stop.name:
                raise AmapParseError(f"线路 {line.id} 第 {expected} 站缺少名称")
            try:
                sequence = int(stop.sequence) if stop.sequence is not None else expected
            except (TypeError, ValueError) as exc:
                raise AmapParseError(f"线路 {line.id} 站序格式错误") from exc
            if sequence < 1 or sequence in seen_sequences:
                raise AmapParseError(f"线路 {line.id} 站序必须从 1 开始且不重复")
            seen_sequences.add(sequence)
            longitude, latitude = _coordinates(stop.location, f"线路 {line.id} 第 {sequence} 站")
            stops.append(
                ParsedAmapStop(
                    amap_stop_id=stop.id,
                    stop_name=stop.name,
                    longitude=longitude,
                    latitude=latitude,
                    sequence_no=sequence,
                )
            )
        stops.sort(key=lambda item: item.sequence_no or 0)
        if [stop.sequence_no for stop in stops] != list(range(1, len(stops) + 1)):
            raise AmapParseError(f"线路 {line.id} 站序不连续")
        result.append(
            ParsedAmapLine(
                amap_line_id=line.id,
                line_name=_line_name(line.name),
                direction=direction,
                start_stop_name=line.start_stop,
                end_stop_name=line.end_stop,
                first_departure_time=_hhmm(line.start_time, f"线路 {line.id} 首班"),
                last_departure_time=_hhmm(line.end_time, f"线路 {line.id} 末班"),
                stops=tuple(stops),
            )
        )
    return result


def load_amap_stops(path: str | Path) -> list[ParsedAmapStop]:
    return parse_amap_stop_response(AmapStopResponse.model_validate_json(Path(path).read_text()))


def load_amap_lines(path: str | Path) -> list[ParsedAmapLine]:
    return parse_amap_line_response(AmapLineResponse.model_validate_json(Path(path).read_text()))


parse_stop_response = parse_amap_stop_response
parse_line_response = parse_amap_line_response
