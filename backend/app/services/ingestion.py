"""Transactional, idempotent ingestion for parsed Amap stop and line responses."""

from dataclasses import dataclass, field
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from typing import Any, Literal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.logging import redact_sensitive
from app.core.time import now_shanghai, to_mysql_datetime
from app.db.session import get_session_factory
from app.integrations.amap.parser import (
    ParsedLine,
    ParsedLineStop,
    ParsedStop,
    parse_line_response,
    parse_stop_response,
)
from app.integrations.amap.schemas import AmapLineResponseDTO, AmapStopResponseDTO
from app.models.ingestion import IngestionRun
from app.models.transit import BusLine, BusLinePathPoint, BusLineStop, BusStop

TriggerType = Literal["sample_import", "manual", "user_request"]
RunStatus = Literal["success", "partial", "failed"]


class IngestionError(RuntimeError):
    pass


class IngestionConflict(IngestionError):
    pass


@dataclass(slots=True)
class ImportStats:
    received_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0

    def merge(self, other: "ImportStats") -> None:
        self.inserted_count += other.inserted_count
        self.updated_count += other.updated_count
        self.skipped_count += other.skipped_count
        self.failed_count += other.failed_count


@dataclass(frozen=True, slots=True)
class ImportOutcome:
    ingestion_run_id: int
    status: RunStatus
    stats: ImportStats
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


def distance_meters(
    longitude_a: Decimal,
    latitude_a: Decimal,
    longitude_b: Decimal,
    latitude_b: Decimal,
) -> float:
    """Return the Haversine distance between two longitude/latitude points."""

    lon_a, lat_a, lon_b, lat_b = map(
        radians,
        (float(longitude_a), float(latitude_a), float(longitude_b), float(latitude_b)),
    )
    delta_lon = lon_b - lon_a
    delta_lat = lat_b - lat_a
    haversine = sin(delta_lat / 2) ** 2 + cos(lat_a) * cos(lat_b) * sin(delta_lon / 2) ** 2
    return 6371000 * 2 * asin(sqrt(haversine))


def summarize_messages(messages: list[str], *, limit: int = 2000) -> str | None:
    if not messages:
        return None
    return redact_sensitive(" | ".join(messages))[:limit]


def sanitize_request_keyword(value: str | None, *, limit: int = 255) -> str | None:
    if value is None:
        return None
    return redact_sensitive(value)[:limit]


def determine_status(
    *, successful_records: int, errors: list[str], recoverable_errors: bool = False
) -> RunStatus:
    if not errors:
        return "success"
    if recoverable_errors:
        return "partial"
    return "partial" if successful_records > 0 else "failed"


class IngestionService:
    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        self.session_factory = session_factory or get_session_factory()

    def import_stop_response(
        self,
        response: AmapStopResponseDTO | dict[str, Any],
        *,
        trigger_type: TriggerType,
        request_keyword: str | None,
        city_code: str | None,
        ingestion_run_id: int | None = None,
    ) -> ImportOutcome:
        run_id = ingestion_run_id or self._create_run(
            endpoint="stopname", trigger_type=trigger_type,
            request_keyword=request_keyword, city_code=city_code,
        )
        try:
            parsed_stops = parse_stop_response(response)
        except Exception as exc:
            self._finish_failed_run(run_id, exc)
            raise IngestionError(f"高德站点响应解析失败: {exc}") from exc

        stats = ImportStats(received_count=len(parsed_stops))
        errors: list[str] = []
        successful_records = 0
        try:
            with self.session_factory() as session:
                for stop in parsed_stops:
                    record_stats = ImportStats()
                    try:
                        with session.begin_nested():
                            _, inserted = self._upsert_stop(
                                session,
                                stop,
                                ingestion_run_id=run_id,
                                fallback_city_code=city_code,
                            )
                            if inserted:
                                record_stats.inserted_count += 1
                            else:
                                record_stats.updated_count += 1
                    except IngestionConflict as exc:
                        stats.skipped_count += 1
                        stats.failed_count += 1
                        errors.append(str(exc))
                    else:
                        successful_records += 1
                        stats.merge(record_stats)
                session.commit()
        except Exception as exc:
            self._finish_failed_run(run_id, exc, received_count=stats.received_count)
            raise IngestionError(f"高德站点数据入库失败: {exc}") from exc

        status = determine_status(
            successful_records=successful_records,
            errors=errors,
            recoverable_errors=True,
        )
        self._finish_run(run_id, status=status, stats=stats, messages=errors)
        return ImportOutcome(run_id, status, stats, tuple(errors))

    def import_line_response(
        self,
        response: AmapLineResponseDTO | dict[str, Any],
        *,
        trigger_type: TriggerType,
        request_keyword: str | None,
        city_code: str | None,
        amap_line_ids: set[str] | None = None,
        ingestion_run_id: int | None = None,
    ) -> ImportOutcome:
        run_id = ingestion_run_id or self._create_run(
            endpoint="linename", trigger_type=trigger_type,
            request_keyword=request_keyword, city_code=city_code,
        )
        try:
            parsed_lines = parse_line_response(response)
            if amap_line_ids is not None:
                parsed_lines = [
                    line for line in parsed_lines if line.amap_line_id in amap_line_ids
                ]
        except Exception as exc:
            self._finish_failed_run(run_id, exc)
            raise IngestionError(f"高德线路响应解析失败: {exc}") from exc

        stats = ImportStats(received_count=len(parsed_lines))
        errors: list[str] = []
        warnings = [warning for line in parsed_lines for warning in line.warnings]
        successful_records = 0
        try:
            with self.session_factory() as session:
                for line in parsed_lines:
                    record_stats = ImportStats()
                    try:
                        with session.begin_nested():
                            self._upsert_line(
                                session,
                                line,
                                ingestion_run_id=run_id,
                                stats=record_stats,
                            )
                    except IngestionConflict as exc:
                        stats.skipped_count += 1
                        stats.failed_count += 1
                        errors.append(str(exc))
                    else:
                        successful_records += 1
                        stats.merge(record_stats)
                session.commit()
        except Exception as exc:
            self._finish_failed_run(run_id, exc, received_count=stats.received_count)
            raise IngestionError(f"高德线路数据入库失败: {exc}") from exc

        status = determine_status(
            successful_records=successful_records,
            errors=errors,
            recoverable_errors=True,
        )
        self._finish_run(
            run_id,
            status=status,
            stats=stats,
            messages=[*errors, *warnings],
        )
        return ImportOutcome(run_id, status, stats, tuple(errors), tuple(warnings))

    def _create_run(
        self,
        *,
        endpoint: Literal["stopname", "linename", "lineid"],
        trigger_type: TriggerType,
        request_keyword: str | None,
        city_code: str | None,
    ) -> int:
        with self.session_factory() as session, session.begin():
            run = IngestionRun(
                endpoint=endpoint,
                trigger_type=trigger_type,
                request_keyword=sanitize_request_keyword(request_keyword),
                city_code=city_code,
                status="running",
            )
            session.add(run)
            session.flush()
            run_id = run.id
        return run_id

    def _finish_failed_run(
        self, run_id: int, error: Exception, *, received_count: int = 0
    ) -> None:
        stats = ImportStats(received_count=received_count, failed_count=1)
        self._finish_run(run_id, status="failed", stats=stats, messages=[str(error)])

    def _finish_run(
        self,
        run_id: int,
        *,
        status: RunStatus,
        stats: ImportStats,
        messages: list[str],
    ) -> None:
        with self.session_factory() as session, session.begin():
            run = session.get(IngestionRun, run_id)
            if run is None:
                raise IngestionError(f"导入运行 {run_id} 不存在")
            run.status = status
            run.finished_at = to_mysql_datetime(now_shanghai())
            run.received_count = stats.received_count
            run.inserted_count = stats.inserted_count
            run.updated_count = stats.updated_count
            run.skipped_count = stats.skipped_count
            run.failed_count = stats.failed_count
            run.error_message = summarize_messages(messages)

    def _upsert_stop(
        self,
        session: Session,
        parsed: ParsedStop | ParsedLineStop,
        *,
        ingestion_run_id: int,
        fallback_city_code: str | None,
    ) -> tuple[BusStop, bool]:
        stop: BusStop | None = None
        if parsed.amap_stop_id:
            stop = session.scalar(
                select(BusStop).where(BusStop.amap_stop_id == parsed.amap_stop_id)
            )
        parsed_city_code = parsed.city_code if isinstance(parsed, ParsedStop) else None
        if stop is None and parsed.amap_stop_id is None:
            city_code = parsed_city_code or fallback_city_code
            query = select(BusStop).where(
                BusStop.normalized_name == parsed.normalized_name,
                BusStop.city_code == city_code,
            )
            candidates = [
                candidate
                for candidate in session.scalars(query)
                if distance_meters(
                    candidate.longitude,
                    candidate.latitude,
                    parsed.longitude,
                    parsed.latitude,
                )
                <= 50
            ]
            if len(candidates) > 1:
                raise IngestionConflict(
                    f"站点 {parsed.stop_name} 在 50 米内存在多个候选，未自动合并"
                )
            if candidates:
                stop = candidates[0]

        inserted = stop is None
        if stop is None:
            stop = BusStop(
                amap_stop_id=parsed.amap_stop_id,
                stop_name=parsed.stop_name,
                normalized_name=parsed.normalized_name,
                longitude=parsed.longitude,
                latitude=parsed.latitude,
                city_code=parsed_city_code or fallback_city_code,
                line_membership_status="unknown",
                last_ingestion_run_id=ingestion_run_id,
                is_active=True,
            )
            session.add(stop)
        else:
            # A line response may use direction-specific boarding coordinates for an
            # existing stop. Only the canonical stop response may replace its identity.
            if isinstance(parsed, ParsedStop):
                if parsed.amap_stop_id and stop.amap_stop_id is None:
                    stop.amap_stop_id = parsed.amap_stop_id
                stop.stop_name = parsed.stop_name
                stop.normalized_name = parsed.normalized_name
                stop.longitude = parsed.longitude
                stop.latitude = parsed.latitude
                stop.city_code = parsed_city_code or fallback_city_code or stop.city_code
                stop.last_ingestion_run_id = ingestion_run_id
        session.flush()
        if isinstance(parsed, ParsedStop):
            confirmed_ids = set(
                session.scalars(
                    select(BusLine.amap_line_id)
                    .join(BusLineStop, BusLineStop.line_id == BusLine.id)
                    .where(BusLineStop.stop_id == stop.id)
                )
            )
            unresolved = [
                {
                    "amap_line_id": summary.amap_line_id,
                    "line_name": summary.line_name,
                    "amap_name": summary.amap_name,
                    "start_stop_name": summary.start_stop_name,
                    "end_stop_name": summary.end_stop_name,
                    "reason": None,
                }
                for summary in parsed.line_summaries
                if summary.amap_line_id not in confirmed_ids
            ]
            stop.unresolved_line_summaries = unresolved or None
            stop.line_membership_status = "partial" if unresolved else "complete"
            stop.lines_checked_at = to_mysql_datetime(now_shanghai())
        return stop, inserted

    @staticmethod
    def _confirm_line_summary(stop: BusStop, amap_line_id: str) -> None:
        if stop.unresolved_line_summaries is None:
            return
        remaining = [
            summary
            for summary in stop.unresolved_line_summaries
            if summary.get("amap_line_id") != amap_line_id
        ]
        if len(remaining) == len(stop.unresolved_line_summaries):
            return
        stop.unresolved_line_summaries = remaining or None
        stop.line_membership_status = "partial" if remaining else "complete"
        stop.lines_checked_at = to_mysql_datetime(now_shanghai())

    def _upsert_line(
        self,
        session: Session,
        parsed: ParsedLine,
        *,
        ingestion_run_id: int,
        stats: ImportStats,
    ) -> BusLine:
        line = session.scalar(
            select(BusLine).where(BusLine.amap_line_id == parsed.amap_line_id)
        )
        inserted = line is None
        if line is None:
            line = BusLine(
                amap_line_id=parsed.amap_line_id,
                line_name=parsed.line_name,
                amap_name=parsed.amap_name,
                polyline_raw=parsed.polyline_raw,
                last_ingestion_run_id=ingestion_run_id,
                is_active=True,
            )
            session.add(line)

        line.amap_reverse_line_id = parsed.amap_reverse_line_id
        line.line_name = parsed.line_name
        line.amap_name = parsed.amap_name
        line.amap_type = parsed.amap_type
        line.city_code = parsed.city_code
        line.start_stop_name = parsed.start_stop_name
        line.end_stop_name = parsed.end_stop_name
        line.first_departure_time = parsed.first_departure_time
        line.last_departure_time = parsed.last_departure_time
        line.loop_flag = parsed.loop_flag
        line.amap_status = parsed.amap_status
        line.company_name = parsed.company_name
        line.distance_km = parsed.distance_km
        line.basic_price = parsed.basic_price
        line.total_price = parsed.total_price
        line.bounds_raw = parsed.bounds_raw
        line.polyline_raw = parsed.polyline_raw
        line.last_ingestion_run_id = ingestion_run_id
        session.flush()

        if inserted:
            stats.inserted_count += 1
        else:
            stats.updated_count += 1

        session.execute(delete(BusLineStop).where(BusLineStop.line_id == line.id))
        session.execute(
            delete(BusLinePathPoint).where(BusLinePathPoint.line_id == line.id)
        )

        for parsed_stop in parsed.stops:
            stop, stop_inserted = self._upsert_stop(
                session,
                parsed_stop,
                ingestion_run_id=ingestion_run_id,
                fallback_city_code=parsed.city_code,
            )
            stats.inserted_count += int(stop_inserted)
            stats.updated_count += int(not stop_inserted)
            session.add(
                BusLineStop(
                    line_id=line.id,
                    stop_id=stop.id,
                    sequence_no=parsed_stop.sequence_no,
                    amap_stop_id_snapshot=parsed_stop.amap_stop_id,
                    ingestion_run_id=ingestion_run_id,
                )
            )
            self._confirm_line_summary(stop, parsed.amap_line_id)
        stats.inserted_count += len(parsed.stops)

        session.add_all(
            [
                BusLinePathPoint(
                    line_id=line.id,
                    sequence_no=point.sequence_no,
                    longitude=point.longitude,
                    latitude=point.latitude,
                    ingestion_run_id=ingestion_run_id,
                )
                for point in parsed.path_points
            ]
        )
        stats.inserted_count += len(parsed.path_points)
        session.flush()
        return line
