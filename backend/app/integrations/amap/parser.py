"""Pure parsing and validation for Amap bus stop and line responses."""

import json
import unicodedata
from dataclasses import dataclass
from datetime import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.integrations.amap.schemas import (
    AmapLineResponseDTO,
    AmapStopResponseDTO,
)


class AmapParseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ParsedLineSummary:
    amap_line_id: str
    amap_name: str
    line_name: str
    start_stop_name: str | None
    end_stop_name: str | None


@dataclass(frozen=True, slots=True)
class ParsedStop:
    amap_stop_id: str | None
    stop_name: str
    normalized_name: str
    longitude: Decimal
    latitude: Decimal
    city_code: str | None
    adcode: str | None
    line_summaries: tuple[ParsedLineSummary, ...]


@dataclass(frozen=True, slots=True)
class ParsedLineStop:
    amap_stop_id: str | None
    stop_name: str
    normalized_name: str
    longitude: Decimal
    latitude: Decimal
    sequence_no: int


@dataclass(frozen=True, slots=True)
class ParsedPathPoint:
    longitude: Decimal
    latitude: Decimal
    sequence_no: int


@dataclass(frozen=True, slots=True)
class ParsedLine:
    amap_line_id: str
    amap_reverse_line_id: str | None
    line_name: str
    amap_name: str
    amap_type: str | None
    city_code: str | None
    start_stop_name: str | None
    end_stop_name: str | None
    first_departure_time: time | None
    last_departure_time: time | None
    loop_flag: bool | None
    amap_status: str | None
    company_name: str | None
    distance_km: Decimal | None
    basic_price: Decimal | None
    total_price: Decimal | None
    bounds_raw: str | None
    ui_color: str | None
    polyline_raw: str
    stops: tuple[ParsedLineStop, ...]
    path_points: tuple[ParsedPathPoint, ...]
    warnings: tuple[str, ...]


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(normalized.split()).casefold()


def _required_text(value: str | None, context: str) -> str:
    if value is None or not value.strip():
        raise AmapParseError(f"{context} 缺少必填文本")
    return value.strip()


def _line_name(amap_name: str) -> str:
    name = amap_name.split("(", 1)[0].strip()
    return name or amap_name.strip()


def _coordinate(value: str | None, context: str) -> tuple[Decimal, Decimal]:
    raw = _required_text(value, context)
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 2:
        raise AmapParseError(f"{context} 坐标格式错误: {raw!r}")
    try:
        longitude, latitude = (Decimal(part) for part in parts)
    except InvalidOperation as exc:
        raise AmapParseError(f"{context} 坐标格式错误: {raw!r}") from exc
    if not Decimal(-180) <= longitude <= Decimal(180):
        raise AmapParseError(f"{context} 经度越界")
    if not Decimal(-90) <= latitude <= Decimal(90):
        raise AmapParseError(f"{context} 纬度越界")
    return longitude, latitude


def _optional_decimal(
    value: str | None, context: str, warnings: list[str]
) -> Decimal | None:
    if value is None or not value.strip():
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        warnings.append(f"{context} 数值无法解析: {value!r}")
        return None


def _optional_time(value: str | None, context: str, warnings: list[str]) -> time | None:
    if value is None or not value.strip():
        return None
    digits = value.strip().replace(":", "")
    if len(digits) != 4 or not digits.isdigit():
        warnings.append(f"{context} 时间无法解析: {value!r}")
        return None
    hour, minute = int(digits[:2]), int(digits[2:])
    if hour > 23 or minute > 59:
        warnings.append(f"{context} 时间无法解析: {value!r}")
        return None
    return time(hour, minute)


def _optional_loop(value: str | None, context: str, warnings: list[str]) -> bool | None:
    if value is None or not value.strip():
        return None
    if value == "1":
        return True
    if value == "0":
        return False
    warnings.append(f"{context} loop 无法解析: {value!r}")
    return None


def _validate_business_status(status: str | None, info: str | None, infocode: str | None) -> None:
    if status != "1":
        raise AmapParseError(f"高德业务错误 {infocode or 'unknown'}: {info or '未知错误'}")


def parse_stop_response(
    data: AmapStopResponseDTO | dict[str, Any],
) -> list[ParsedStop]:
    response = (
        data if isinstance(data, AmapStopResponseDTO) else AmapStopResponseDTO.model_validate(data)
    )
    _validate_business_status(response.status, response.info, response.infocode)

    result: list[ParsedStop] = []
    for index, stop in enumerate(response.busstops, start=1):
        stop_name = _required_text(stop.name, f"第 {index} 个站点")
        longitude, latitude = _coordinate(stop.location, f"站点 {stop_name}")
        summaries: list[ParsedLineSummary] = []
        for summary_index, summary in enumerate(stop.buslines, start=1):
            amap_line_id = _required_text(
                summary.id, f"站点 {stop_name} 第 {summary_index} 条线路摘要"
            )
            amap_name = _required_text(
                summary.name, f"站点 {stop_name} 第 {summary_index} 条线路摘要"
            )
            summaries.append(
                ParsedLineSummary(
                    amap_line_id=amap_line_id,
                    amap_name=amap_name,
                    line_name=_line_name(amap_name),
                    start_stop_name=summary.start_stop,
                    end_stop_name=summary.end_stop,
                )
            )
        result.append(
            ParsedStop(
                amap_stop_id=stop.id,
                stop_name=stop_name,
                normalized_name=normalize_name(stop_name),
                longitude=longitude,
                latitude=latitude,
                city_code=stop.citycode,
                adcode=stop.adcode,
                line_summaries=tuple(summaries),
            )
        )
    return result


def parse_line_response(
    data: AmapLineResponseDTO | dict[str, Any],
) -> list[ParsedLine]:
    response = (
        data if isinstance(data, AmapLineResponseDTO) else AmapLineResponseDTO.model_validate(data)
    )
    _validate_business_status(response.status, response.info, response.infocode)

    parsed: list[ParsedLine] = []
    for index, line in enumerate(response.buslines, start=1):
        amap_line_id = _required_text(line.id, f"第 {index} 条线路")
        amap_name = _required_text(line.name, f"线路 {amap_line_id}")
        polyline_raw = _required_text(line.polyline, f"线路 {amap_line_id} polyline")
        warnings: list[str] = []

        path_points: list[ParsedPathPoint] = []
        for sequence_no, raw_point in enumerate(polyline_raw.split(";"), start=1):
            longitude, latitude = _coordinate(
                raw_point, f"线路 {amap_line_id} 第 {sequence_no} 个轨迹点"
            )
            path_points.append(
                ParsedPathPoint(
                    longitude=longitude,
                    latitude=latitude,
                    sequence_no=sequence_no,
                )
            )
        if len(path_points) < 2:
            raise AmapParseError(f"线路 {amap_line_id} 至少需要两个轨迹点")

        stops: list[ParsedLineStop] = []
        for expected_sequence, stop in enumerate(line.busstops, start=1):
            stop_name = _required_text(
                stop.name, f"线路 {amap_line_id} 第 {expected_sequence} 个站点"
            )
            if stop.sequence is None:
                raise AmapParseError(f"线路 {amap_line_id} 站点 {stop_name} 缺少 sequence")
            try:
                sequence_no = int(stop.sequence)
            except ValueError as exc:
                raise AmapParseError(
                    f"线路 {amap_line_id} 站点 {stop_name} sequence 非整数"
                ) from exc
            if sequence_no != expected_sequence:
                raise AmapParseError(f"线路 {amap_line_id} 站序必须从 1 连续")
            longitude, latitude = _coordinate(
                stop.location, f"线路 {amap_line_id} 站点 {stop_name}"
            )
            stops.append(
                ParsedLineStop(
                    amap_stop_id=stop.id,
                    stop_name=stop_name,
                    normalized_name=normalize_name(stop_name),
                    longitude=longitude,
                    latitude=latitude,
                    sequence_no=sequence_no,
                )
            )
        if not stops:
            raise AmapParseError(f"线路 {amap_line_id} 缺少完整站序")

        parsed.append(
            ParsedLine(
                amap_line_id=amap_line_id,
                amap_reverse_line_id=line.direc,
                line_name=_line_name(amap_name),
                amap_name=amap_name,
                amap_type=line.type,
                city_code=line.citycode,
                start_stop_name=line.start_stop,
                end_stop_name=line.end_stop,
                first_departure_time=_optional_time(
                    line.start_time, f"线路 {amap_line_id} 首班", warnings
                ),
                last_departure_time=_optional_time(
                    line.end_time, f"线路 {amap_line_id} 末班", warnings
                ),
                loop_flag=_optional_loop(
                    line.loop, f"线路 {amap_line_id}", warnings
                ),
                amap_status=line.status,
                company_name=line.company,
                distance_km=_optional_decimal(
                    line.distance, f"线路 {amap_line_id} distance", warnings
                ),
                basic_price=_optional_decimal(
                    line.basic_price, f"线路 {amap_line_id} basic_price", warnings
                ),
                total_price=_optional_decimal(
                    line.total_price, f"线路 {amap_line_id} total_price", warnings
                ),
                bounds_raw=line.bounds,
                ui_color=line.uicolor,
                polyline_raw=polyline_raw,
                stops=tuple(stops),
                path_points=tuple(path_points),
                warnings=tuple(warnings),
            )
        )

    by_id = {line.amap_line_id: line for line in parsed}
    for parsed_line in parsed:
        if (
            parsed_line.amap_reverse_line_id is None
            or parsed_line.amap_reverse_line_id not in by_id
        ):
            continue
        reverse = by_id[parsed_line.amap_reverse_line_id]
        if reverse.amap_reverse_line_id != parsed_line.amap_line_id:
            raise AmapParseError(
                f"线路 {parsed_line.amap_line_id} 与 {reverse.amap_line_id} 的 direc 未互指"
            )
    return parsed


def load_stop_sample(path: str | Path) -> list[ParsedStop]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_stop_response(payload)


def load_line_sample(path: str | Path) -> list[ParsedLine]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_line_response(payload)
