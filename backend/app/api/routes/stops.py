"""Stop search and stop-line endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session, get_session_factory
from app.integrations.amap.client import AmapClient
from app.schemas.transit import (
    StopItem,
    StopLinesResponse,
    StopResponse,
    StopSearchResponse,
)
from app.services.on_demand_sync import (
    OnDemandSyncService,
    TransitNotFound,
    TransitUpstreamError,
)
from app.services.transit import TransitService

router = APIRouter(prefix="/stops", tags=["stops"])


def _sync() -> OnDemandSyncService:
    return OnDemandSyncService(get_session_factory(), AmapClient(get_settings()))


def _raise(exc: Exception) -> None:
    if isinstance(exc, (TransitNotFound, TransitUpstreamError)):
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    raise exc


@router.get("/search", response_model=StopSearchResponse)
def search_stops(
    q: str = Query(min_length=1, max_length=150),
    city_code: str = Query(default="021", pattern=r"^[0-9]{3,6}$"),
    limit: int = Query(default=20, ge=1, le=100),
) -> StopSearchResponse:
    if not q.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_REQUEST", "message": "查询关键词不能为空"},
        )
    try:
        items, run_id = _sync().search_stops(query=q, city_code=city_code, limit=limit)
    except (TransitNotFound, TransitUpstreamError) as exc:
        _raise(exc)
    return StopSearchResponse(
        data_source="amap" if run_id else "database",
        ingestion_run_id=run_id,
        items=[StopItem.model_validate(item) for item in items],
    )


@router.get("/{stop_id}", response_model=StopResponse)
def get_stop(
    stop_id: int, session: Session = Depends(get_session)  # noqa: B008
) -> StopResponse:
    stop = TransitService(session).get_stop(stop_id)
    if stop is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "站点不存在"})
    return StopResponse(data_source="database", stop=StopItem.model_validate(stop))


@router.get("/{stop_id}/lines", response_model=StopLinesResponse)
def get_stop_lines(
    stop_id: int,
) -> StopLinesResponse:
    with get_session_factory()() as session:
        transit = TransitService(session)
        stop = transit.get_stop(stop_id)
        if stop is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": "站点不存在"},
            )
        lines = transit.get_lines_for_stop(stop_id)
        unresolved = transit.get_unresolved_lines_for_stop(stop)
        return StopLinesResponse(
            data_source="database",
            stop=transit.stop_item(stop),
            lines=[transit.line_item(line) for line in lines],
            unresolved_summaries=unresolved,
            partial=stop.line_membership_status != "complete",
        )
