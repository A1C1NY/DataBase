"""Response contracts for database-only analytics endpoints."""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

HeatmapMetric = Literal["stop_density", "line_density"]
DistributionBucket = Literal["hour", "day", "weekday_hour"]
ActorScope = Literal["passenger", "all"]


class AnalyticsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HeatmapResponse(AnalyticsSchema):
    data_source: Literal["database"] = "database"
    metric: HeatmapMetric
    grid_size_m: int
    geojson: dict[str, Any]


class StopPopularityItem(AnalyticsSchema):
    stop_id: int
    stop_name: str
    detail_view_count: int = Field(description="站点详情访问次数")
    unique_user_count: int


class StopPopularityResponse(AnalyticsSchema):
    data_source: Literal["database"] = "database"
    metric_name: Literal["站点详情访问次数"] = "站点详情访问次数"
    items: list[StopPopularityItem]


class DistributionItem(AnalyticsSchema):
    bucket: int | date | str
    detail_view_count: int = Field(description="站点详情访问次数")


class StopViewDistributionResponse(AnalyticsSchema):
    data_source: Literal["database"] = "database"
    metric_name: Literal["站点详情访问次数"] = "站点详情访问次数"
    stop_id: int
    stop_name: str
    bucket: DistributionBucket
    actor_scope: ActorScope
    items: list[DistributionItem]
