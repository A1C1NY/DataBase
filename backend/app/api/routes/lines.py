"""Line detail, ordered stops, and map endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.api.dependencies import OptionalCurrentUser, SessionDep
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.integrations.amap.client import AmapClient
from app.schemas.transit import (
    LineMapResponse,
    LineResponse,
    LineSearchResponse,
    LineStopsResponse,
)
from app.services.on_demand_sync import (
    OnDemandSyncService,
    TransitNotFound,
    TransitUpstreamError,
)
from app.services.transit import TransitService
from app.services.view_events import LineViewEventService

router = APIRouter(prefix="/lines", tags=["lines"])


def _sync() -> OnDemandSyncService:
    return OnDemandSyncService(get_session_factory(), AmapClient(get_settings()))


def _raise(exc: Exception) -> None:
    if isinstance(exc, (TransitNotFound, TransitUpstreamError)):
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    raise exc


@router.get("/search", response_model=LineSearchResponse)
def search_lines(
    q: str = Query(min_length=1, max_length=150),
    city_code: str = Query(default="021", pattern=r"^[0-9]{3,6}$"),
    limit: int = Query(default=20, ge=1, le=100),
    refresh: bool = Query(default=False, description="强制从高德刷新并增量入库"),
) -> LineSearchResponse:
    if not q.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_REQUEST", "message": "查询关键词不能为空"},
        )
    try:
        items, run_id = _sync().search_lines(
            query=q, city_code=city_code, limit=limit, refresh=refresh
        )
    except (TransitNotFound, TransitUpstreamError) as exc:
        _raise(exc)
    return LineSearchResponse(
        data_source="amap" if run_id else "database",
        ingestion_run_id=run_id,
        items=[TransitService.line_item(item) for item in items],
    )


@router.get("/by-amap/{amap_line_id}", response_model=LineResponse)
def get_line_by_amap(
    amap_line_id: str,
    refresh: bool = Query(default=False),
) -> LineResponse:
    try:
        run_id = _sync().backfill_line(amap_line_id=amap_line_id, refresh=refresh)
        with get_session_factory()() as session:
            line = TransitService(session).get_line_by_amap_id(amap_line_id)
            if line is None:
                raise TransitNotFound("高德和本地数据库均未找到线路")
            return TransitService(session).line_response(
                line,
                data_source="amap" if run_id else "database",
                ingestion_run_id=run_id or None,
            )
    except (TransitNotFound, TransitUpstreamError) as exc:
        _raise(exc)
    raise AssertionError("unreachable")


@router.get("/{line_id}", response_model=LineResponse)
def get_line(line_id: int, session: SessionDep, user: OptionalCurrentUser) -> LineResponse:
    line = LineViewEventService(session).open_line_detail(line_id, user=user)
    if line is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "线路不存在"})
    return TransitService(session).line_response(line, data_source="database")


@router.get("/{line_id}/stops", response_model=LineStopsResponse)
def get_line_stops(line_id: int) -> LineStopsResponse:
    with get_session_factory()() as session:
        transit = TransitService(session)
        line = transit.get_line(line_id)
        if line is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "线路不存在"})
        return transit.line_stops_response(line, data_source="database")


@router.get("/{line_id}/map", response_model=LineMapResponse)
def get_line_map(line_id: int) -> LineMapResponse:
    with get_session_factory()() as session:
        transit = TransitService(session)
        line = transit.get_line(line_id)
        if line is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "线路不存在"})
        return transit.line_map_response(line, data_source="database")
