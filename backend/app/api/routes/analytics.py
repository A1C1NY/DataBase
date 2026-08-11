"""Role-protected, database-only analytics endpoints."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.api.dependencies import AnalystOrAdmin, SessionDep
from app.geo.grid import BoundingBox, parse_bbox
from app.schemas.analytics import (
    ActorScope,
    DistributionBucket,
    HeatmapResponse,
    StopPopularityResponse,
    StopViewDistributionResponse,
)
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _bbox(value: str) -> BoundingBox:
    try:
        return parse_bbox(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_BBOX", "message": str(exc)},
        ) from exc


@router.get("/heatmaps/stops", response_model=HeatmapResponse)
def stop_heatmap(
    session: SessionDep,
    _user: AnalystOrAdmin,
    bbox: str = Query(description="min_lon,min_lat,max_lon,max_lat"),
    grid_size_m: int = Query(default=300, ge=100, le=2000),
) -> HeatmapResponse:
    return AnalyticsService(session).stop_heatmap(_bbox(bbox), grid_size_m)


@router.get("/heatmaps/lines", response_model=HeatmapResponse)
def line_heatmap(
    session: SessionDep,
    _user: AnalystOrAdmin,
    bbox: str = Query(description="min_lon,min_lat,max_lon,max_lat"),
    grid_size_m: int = Query(default=300, ge=100, le=2000),
) -> HeatmapResponse:
    return AnalyticsService(session).line_heatmap(_bbox(bbox), grid_size_m)


@router.get("/stops/popularity", response_model=StopPopularityResponse)
def stop_popularity(
    session: SessionDep,
    _user: AnalystOrAdmin,
    start_at: datetime,
    end_at: datetime,
    limit: int = Query(default=20, ge=1, le=100),
) -> StopPopularityResponse:
    try:
        return AnalyticsService(session).stop_popularity(start_at, end_at, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_TIME_RANGE", "message": str(exc)}) from exc


@router.get("/stops/{stop_id}/view-distribution", response_model=StopViewDistributionResponse)
def stop_view_distribution(
    stop_id: int,
    session: SessionDep,
    _user: AnalystOrAdmin,
    start_at: datetime,
    end_at: datetime,
    bucket: DistributionBucket = "hour",
    actor_scope: ActorScope = "passenger",
) -> StopViewDistributionResponse:
    try:
        response = AnalyticsService(session).stop_view_distribution(
            stop_id, start_at, end_at, bucket, actor_scope
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_TIME_RANGE", "message": str(exc)}) from exc
    if response is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "站点不存在"})
    return response
