"""Transactional import of the three local upstream samples."""

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import now, to_mysql_datetime
from app.integrations.amap.parser import (
    ParsedAmapLine,
    ParsedAmapStop,
    parse_amap_line_response,
    parse_amap_stop_response,
)
from app.integrations.amap.schemas import AmapLineResponse, AmapStopResponse
from app.integrations.shanghai.parser import (
    ParsedShanghaiResponse,
    parse_shanghai_response,
)
from app.integrations.shanghai.schemas import ShanghaiNearbyResponse
from app.models.ingestion import ArrivalInfo, DispatchCar, DispatchSchedule, IngestionRun
from app.models.transit import Line, LineRoute, Stop


class IngestionError(ValueError):
    pass


def _run(session: Session, source: str, task_type: str, request_key: str | None) -> IngestionRun:
    if request_key is not None:
        existing = session.scalar(
            select(IngestionRun)
            .where(
                IngestionRun.source == source,
                IngestionRun.task_type == task_type,
                IngestionRun.request_key == request_key,
                IngestionRun.status.in_(("success", "partial")),
            )
            .order_by(IngestionRun.id.desc())
        )
        if existing is not None:
            return existing
    record = IngestionRun(
        source=source,
        task_type=task_type,
        trigger_type="manual",
        request_key=request_key,
        status="running",
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def _finish(session: Session, run: IngestionRun, status: str, error: str | None = None) -> None:
    run.status = status
    run.finished_at = to_mysql_datetime(now())
    run.error_message = error[:2000] if error else None
    session.commit()


def _fail(session: Session, run_id: int, error: Exception) -> None:
    session.rollback()
    run = session.get(IngestionRun, run_id)
    if run is not None:
        _finish(session, run, "failed", str(error))


def _find_line_by_amap(session: Session, external_id: str) -> Line | None:
    return session.scalar(select(Line).where(Line.amap_line_id == external_id))


def _find_stop_by_amap(session: Session, external_id: str | None) -> Stop | None:
    if not external_id:
        return None
    return session.scalar(select(Stop).where(Stop.amap_stop_id == external_id))


def _find_stop_by_name(session: Session, name: str) -> Stop | None:
    return session.scalar(select(Stop).where(Stop.stop_name == name))


def _upsert_amap_stop(session: Session, parsed: ParsedAmapStop) -> tuple[Stop, bool]:
    stop = _find_stop_by_amap(session, parsed.amap_stop_id)
    if stop is None and parsed.amap_stop_id is None:
        stop = _find_stop_by_name(session, parsed.stop_name)
    if stop is None:
        stop = Stop(
            stop_name=parsed.stop_name,
            amap_stop_id=parsed.amap_stop_id,
            longitude=parsed.longitude,
            latitude=parsed.latitude,
        )
        session.add(stop)
        session.flush()
        return stop, True
    # An existing external ID is authoritative; updating its descriptive values is safe.
    if stop.amap_stop_id == parsed.amap_stop_id or parsed.amap_stop_id is None:
        stop.stop_name = parsed.stop_name
        stop.longitude = parsed.longitude
        stop.latitude = parsed.latitude
    return stop, False


def _upsert_amap_line(session: Session, parsed: ParsedAmapLine) -> tuple[Line, bool]:
    line = _find_line_by_amap(session, parsed.amap_line_id)
    if line is None:
        line = Line(
            line_name=parsed.line_name,
            direction=parsed.direction,
            amap_line_id=parsed.amap_line_id,
            first_departure_time=parsed.first_departure_time,
            last_departure_time=parsed.last_departure_time,
        )
        session.add(line)
        session.flush()
        return line, True
    line.line_name = parsed.line_name
    line.direction = parsed.direction
    line.first_departure_time = parsed.first_departure_time
    line.last_departure_time = parsed.last_departure_time
    return line, False


def _replace_route(session: Session, line: Line, stops: tuple[ParsedAmapStop, ...]) -> None:
    # The parser has already validated the complete, contiguous sequence.
    session.query(LineRoute).filter(LineRoute.line_id == line.id).delete(
        synchronize_session=False
    )
    for parsed in stops:
        stop, _ = _upsert_amap_stop(session, parsed)
        session.add(
            LineRoute(
                line_id=line.id,
                stop_id=stop.id,
                sequence_no=parsed.sequence_no or 0,
            )
        )


def import_amap_lines(
    session: Session,
    payload: dict[str, Any] | AmapLineResponse,
    *,
    request_key: str | None = None,
) -> IngestionRun:
    run = _run(session, "amap", "line_import", request_key)
    if run.status != "running":
        return run
    run_id = run.id
    try:
        parsed = parse_amap_line_response(payload)
        run.received_count = len(parsed)
        for item in parsed:
            line, inserted = _upsert_amap_line(session, item)
            _replace_route(session, line, item.stops)
            run.inserted_count += int(inserted)
            run.updated_count += int(not inserted)
        session.flush()
        _finish(session, run, "success")
        return run
    except Exception as exc:
        _fail(session, run_id, exc)
        raise


def import_amap_stops(
    session: Session,
    payload: dict[str, Any] | AmapStopResponse,
    *,
    request_key: str | None = None,
) -> IngestionRun:
    run = _run(session, "amap", "stop_import", request_key)
    if run.status != "running":
        return run
    run_id = run.id
    try:
        parsed = parse_amap_stop_response(payload)
        run.received_count = len(parsed)
        for item in parsed:
            _, inserted = _upsert_amap_stop(session, item)
            run.inserted_count += int(inserted)
            run.updated_count += int(not inserted)
        session.flush()
        _finish(session, run, "success")
        return run
    except Exception as exc:
        _fail(session, run_id, exc)
        raise


def _find_shanghai_line(session: Session, line_id: str, direction: int) -> Line | None:
    return session.scalar(
        select(Line).where(Line.shanghai_line_id == line_id, Line.direction == direction)
    )


def _upsert_shanghai_line(session: Session, parsed: Any) -> tuple[Line, bool]:
    line = _find_shanghai_line(session, parsed.line_id, parsed.direction)
    if line is None:
        line = session.scalar(
            select(Line).where(
                Line.shanghai_line_id.is_(None),
                Line.line_name == parsed.line_name,
                Line.direction == parsed.direction,
            )
        )
    if line is None:
        line = Line(
            line_name=parsed.line_name,
            direction=parsed.direction,
            line_type=parsed.line_type,
            shanghai_line_id=parsed.line_id,
            first_departure_time=parsed.first_departure_time,
            last_departure_time=parsed.last_departure_time,
        )
        session.add(line)
        session.flush()
        return line, True
    if line.shanghai_line_id is None:
        line.shanghai_line_id = parsed.line_id
    line.line_name = parsed.line_name
    line.line_type = parsed.line_type
    line.first_departure_time = parsed.first_departure_time
    line.last_departure_time = parsed.last_departure_time
    return line, False


def _resolve_shanghai_stop(
    session: Session, line: Line, stop_id: str | None, name: str, longitude: Any, latitude: Any
) -> tuple[Stop, LineRoute | None, bool]:
    route = None
    if stop_id:
        route = session.scalar(
            select(LineRoute).where(
                LineRoute.line_id == line.id, LineRoute.shanghai_stop_id == stop_id
            )
        )
    stop = route.stop if route is not None else _find_stop_by_name(session, name)
    inserted = False
    if stop is None:
        stop = Stop(stop_name=name, longitude=longitude, latitude=latitude)
        session.add(stop)
        session.flush()
        inserted = True
    if route is None and stop_id:
        # Do not invent a route sequence. A sequence is added only by the Amap import.
        route = session.scalar(
            select(LineRoute).where(LineRoute.line_id == line.id, LineRoute.stop_id == stop.id)
        )
        if route is not None and route.shanghai_stop_id is None:
            route.shanghai_stop_id = stop_id
    return stop, route, inserted


def import_shanghai(
    session: Session,
    payload: dict[str, Any] | ShanghaiNearbyResponse,
    collected_at: datetime,
    *,
    request_key: str | None = None,
) -> IngestionRun:
    run = _run(session, "shanghai", "nearby_import", request_key)
    if run.status != "running":
        return run
    run_id = run.id
    try:
        parsed: ParsedShanghaiResponse = parse_shanghai_response(payload, collected_at)
        run.received_count = len(parsed.entries)
        line_map: dict[tuple[str, int], Line] = {}
        arrival_keys: set[tuple[int, int]] = set()
        for entry in parsed.entries:
            line, inserted_line = _upsert_shanghai_line(session, entry.line)
            line_map[entry.line.key] = line
            stop, route, inserted_stop = _resolve_shanghai_stop(
                session,
                line,
                entry.stop.stop_id,
                entry.stop.stop_name,
                entry.stop.longitude,
                entry.stop.latitude,
            )
            run.inserted_count += int(inserted_line or inserted_stop)
            run.updated_count += int(not inserted_line and not inserted_stop)
            if entry.arrival is not None:
                arrival_key = (line.id, stop.id)
                if arrival_key in arrival_keys:
                    run.skipped_count += 1
                    continue
                arrival_keys.add(arrival_key)
                session.add(
                    ArrivalInfo(
                        ingestion_run_id=run.id,
                        line_id=line.id,
                        stop_id=stop.id,
                        collected_at=to_mysql_datetime(collected_at),
                        source_up_down=entry.arrival.source_up_down,
                        current_bus_distance_m=entry.arrival.current_bus_distance_m,
                        current_bus_arrival_min=entry.arrival.current_bus_arrival_min,
                        current_bus_comfort=entry.arrival.current_bus_comfort,
                        current_bus_stop_count=entry.arrival.current_bus_stop_count,
                        current_license_plate=entry.arrival.current_license_plate,
                        current_barrier_free=entry.arrival.current_barrier_free,
                        next_bus_distance_m=entry.arrival.next_bus_distance_m,
                        next_bus_arrival_min=entry.arrival.next_bus_arrival_min,
                        next_bus_stop_count=entry.arrival.next_bus_stop_count,
                        next_license_plate=entry.arrival.next_license_plate,
                        next_barrier_free=entry.arrival.next_barrier_free,
                    )
                )
        for schedule in parsed.schedules:
            schedule_line = line_map.get(schedule.line_key) or _find_shanghai_line(
                session, *schedule.line_key
            )
            if schedule_line is None:
                continue
            dispatch = DispatchSchedule(
                ingestion_run_id=run.id,
                line_id=schedule_line.id,
                collected_at=to_mysql_datetime(collected_at),
                schedule_code=schedule.schedule_code,
                message_default=schedule.message_default,
                message_short=schedule.message_short,
            )
            session.add(dispatch)
            session.flush()
            for car in schedule.cars:
                session.add(
                    DispatchCar(
                        schedule_id=dispatch.id,
                        sequence_no=car.sequence_no,
                        vehicle_text=car.vehicle_text,
                        is_barrier_free=car.is_barrier_free,
                        planned_departure_at=(
                            to_mysql_datetime(car.planned_departure_at)
                            if car.planned_departure_at
                            else None
                        ),
                        countdown_text=car.countdown_text,
                        countdown_seconds=car.countdown_seconds,
                    )
                )
        session.flush()
        _finish(session, run, "partial" if parsed.issues else "success", "; ".join(parsed.issues))
        return run
    except Exception as exc:
        _fail(session, run_id, exc)
        raise


def import_samples(
    session: Session,
    amap_stop_path: str | Path,
    amap_line_path: str | Path,
    shanghai_path: str | Path,
    *,
    collected_at: datetime | None = None,
) -> list[IngestionRun]:
    """Import all three samples, reusing the production DTOs and parsers."""
    collected = collected_at or now()
    line_payload = AmapLineResponse.model_validate_json(Path(amap_line_path).read_text())
    stop_payload = AmapStopResponse.model_validate_json(Path(amap_stop_path).read_text())
    shanghai_payload = ShanghaiNearbyResponse.model_validate_json(Path(shanghai_path).read_text())
    return [
        import_amap_lines(session, line_payload, request_key=str(amap_line_path)),
        import_amap_stops(session, stop_payload, request_key=str(amap_stop_path)),
        import_shanghai(
            session,
            shanghai_payload,
            collected,
            request_key=str(shanghai_path),
        ),
    ]
