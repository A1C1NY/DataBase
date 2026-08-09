"""High-level database-first reads with transactional Amap backfilling."""

from collections.abc import Callable
from typing import Literal, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.logging import redact_sensitive
from app.core.time import now_shanghai, to_mysql_datetime
from app.integrations.amap.client import AmapClient, AmapClientError
from app.models.transit import BusLine, BusStop
from app.services.ingestion import IngestionError, IngestionService
from app.services.transit import TransitService


class TransitUpstreamError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class TransitNotFound(RuntimeError):
    code = "NOT_FOUND_AFTER_AMAP"
    status_code = 404


T = TypeVar("T")


class OnDemandSyncService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        amap_client: AmapClient,
    ) -> None:
        self.session_factory = session_factory
        self.amap_client = amap_client
        self.ingestion = IngestionService(session_factory)

    def _request(
        self,
        endpoint: Literal["stopname", "linename", "lineid"],
        keyword: str,
        city_code: str | None,
        callback: Callable[[], T],
    ) -> tuple[T, int]:
        run_id = self.ingestion._create_run(
            endpoint=endpoint,
            trigger_type="user_request",
            request_keyword=keyword,
            city_code=city_code,
        )
        try:
            return callback(), run_id
        except AmapClientError as exc:
            self.ingestion._finish_failed_run(run_id, exc)
            if exc.kind in {"configuration", "unavailable", "invalid_response"}:
                raise TransitUpstreamError("AMAP_UNAVAILABLE", str(exc), status_code=503) from exc
            if exc.kind == "business_error":
                raise TransitUpstreamError("AMAP_BUSINESS_ERROR", str(exc), status_code=502) from exc
            raise TransitUpstreamError("INVALID_REQUEST", str(exc), status_code=422) from exc
        except Exception as exc:
            self.ingestion._finish_failed_run(run_id, exc)
            raise TransitUpstreamError(
                "AMAP_UNAVAILABLE", "高德响应格式无效", status_code=503
            ) from exc

    @staticmethod
    def _ingestion_failure(exc: IngestionError) -> TransitUpstreamError:
        return TransitUpstreamError(
            "AMAP_UNAVAILABLE", str(exc), status_code=503
        )

    def search_stops(self, *, query: str, city_code: str, limit: int) -> tuple[list[BusStop], int | None]:
        with self.session_factory() as session:
            local = TransitService(session).search_stops(query, city_code, limit)
            if local:
                return local, None

        response, run_id = self._request(
            "stopname", query, city_code,
            lambda: self.amap_client.query_stop(keywords=query, city=city_code),
        )
        try:
            outcome = self.ingestion.import_stop_response(
                response, trigger_type="user_request", request_keyword=query,
                city_code=city_code, ingestion_run_id=run_id,
            )
        except IngestionError as exc:
            raise self._ingestion_failure(exc) from exc
        with self.session_factory() as session:
            items = TransitService(session).search_stops(query, city_code, limit)
        if not items:
            raise TransitNotFound("高德和本地数据库均未找到站点")
        return items, outcome.ingestion_run_id

    def search_lines(
        self, *, query: str, city_code: str, limit: int
    ) -> tuple[list[BusLine], int | None]:
        with self.session_factory() as session:
            local = TransitService(session).search_lines(query, city_code, limit)
            if local:
                return local, None

        response, run_id = self._request(
            "linename",
            query,
            city_code,
            lambda: self.amap_client.query_line(keywords=query, city=city_code),
        )
        try:
            outcome = self.ingestion.import_line_response(
                response,
                trigger_type="user_request",
                request_keyword=query,
                city_code=city_code,
                ingestion_run_id=run_id,
            )
        except IngestionError as exc:
            raise self._ingestion_failure(exc) from exc
        with self.session_factory() as session:
            items = TransitService(session).search_lines(query, city_code, limit)
        if not items:
            raise TransitNotFound("高德和本地数据库均未找到线路")
        return items, outcome.ingestion_run_id

    def _record_line_summary_reason(self, amap_line_id: str, reason: str) -> None:
        safe_reason = redact_sensitive(reason)[:500]
        with self.session_factory() as session, session.begin():
            stops = session.scalars(
                select(BusStop).where(BusStop.unresolved_line_summaries.is_not(None))
            )
            for stop in stops:
                updated: list[dict[str, str | None]] = []
                changed = False
                for summary in stop.unresolved_line_summaries or []:
                    item = dict(summary)
                    if item.get("amap_line_id") == amap_line_id:
                        item["reason"] = safe_reason
                        changed = True
                    updated.append(item)
                if changed:
                    stop.unresolved_line_summaries = updated
                    stop.lines_checked_at = to_mysql_datetime(now_shanghai())

    def backfill_line(self, *, amap_line_id: str, refresh: bool = False) -> int:
        with self.session_factory() as session:
            transit = TransitService(session)
            existing = transit.get_line_by_amap_id(amap_line_id)
            if existing is not None and not refresh and transit.is_line_complete(existing):
                return 0
        try:
            response, run_id = self._request(
                "lineid",
                amap_line_id,
                None,
                lambda: self.amap_client.query_line_by_id(amap_line_id=amap_line_id),
            )
        except TransitUpstreamError as exc:
            self._record_line_summary_reason(amap_line_id, str(exc))
            raise
        try:
            outcome = self.ingestion.import_line_response(
                response,
                trigger_type="user_request",
                request_keyword=amap_line_id,
                city_code=None,
                amap_line_ids={amap_line_id},
                ingestion_run_id=run_id,
            )
        except IngestionError as exc:
            self._record_line_summary_reason(amap_line_id, str(exc))
            raise self._ingestion_failure(exc) from exc
        with self.session_factory() as session:
            found = TransitService(session).get_line_by_amap_id(amap_line_id) is not None
        if not found:
            self._record_line_summary_reason(
                amap_line_id, "高德线路 ID 查询未返回目标线路"
            )
            raise TransitNotFound("高德和本地数据库均未找到线路")
        self._record_line_summary_reason(
            amap_line_id, "完整线路未包含该站点，摘要仍未确认"
        )
        return outcome.ingestion_run_id
