"""Line detail, ordered stops, and map endpoints."""

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.integrations.amap.client import AmapClient
from app.schemas.transit import LineMapResponse, LineResponse, LineStopsResponse
from app.services.on_demand_sync import (
    OnDemandSyncService,
    TransitNotFound,
    TransitUpstreamError,
)
from app.services.transit import TransitService

router = APIRouter(prefix="/lines", tags=["lines"])


def _sync() -> OnDemandSyncService:
    return OnDemandSyncService(get_session_factory(), AmapClient(get_settings()))


def _raise(exc: Exception) -> None:
    if isinstance(exc, (TransitNotFound, TransitUpstreamError)):
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    raise exc


@router.get("/by-amap/{amap_line_id}", response_model=LineResponse)
def get_line_by_amap(
    amap_line_id: str,
) -> LineResponse:
    try:
        with get_session_factory()() as session:
            transit = TransitService(session)
            line = transit.get_line_by_amap_id(amap_line_id)
            if line is not None:
                return transit.line_response(line, data_source="database")
        run_id = _sync().backfill_line(amap_line_id=amap_line_id)
        with get_session_factory()() as session:
            line = TransitService(session).get_line_by_amap_id(amap_line_id)
            if line is None:
                raise TransitNotFound("高德和本地数据库均未找到线路")
            return TransitService(session).line_response(line, data_source="amap", ingestion_run_id=run_id)
    except (TransitNotFound, TransitUpstreamError) as exc:
        _raise(exc)
    raise AssertionError("unreachable")


@router.get("/{line_id}", response_model=LineResponse)
def get_line(line_id: int) -> LineResponse:
    with get_session_factory()() as session:
        transit = TransitService(session)
        line = transit.get_line(line_id)
        if line is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "线路不存在"})
        return transit.line_response(line, data_source="database")


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
