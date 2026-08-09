"""Response contracts for database-first transit queries."""

from datetime import time
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DataSource = Literal["database", "amap"]


class TransitSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StopItem(TransitSchema):
    id: int
    amap_stop_id: str | None
    stop_name: str
    longitude: Decimal
    latitude: Decimal
    coordinate_system: Literal["GCJ02"] = "GCJ02"
    city_code: str | None


class LineItem(TransitSchema):
    id: int
    amap_line_id: str
    amap_reverse_line_id: str | None
    line_name: str
    amap_name: str
    city_code: str | None
    start_stop_name: str | None
    end_stop_name: str | None
    first_departure_time: time | None
    last_departure_time: time | None
    loop_flag: bool | None
    company_name: str | None
    distance_km: Decimal | None
    basic_price: Decimal | None
    total_price: Decimal | None
    ui_color: str | None


class LineStopItem(TransitSchema):
    sequence_no: int
    stop: StopItem


class UnresolvedLineSummary(TransitSchema):
    amap_line_id: str
    line_name: str
    amap_name: str
    start_stop_name: str | None = None
    end_stop_name: str | None = None
    reason: str | None = None


class StopSearchResponse(TransitSchema):
    data_source: DataSource
    ingestion_run_id: int | None = None
    items: list[StopItem]


class LineSearchResponse(TransitSchema):
    data_source: DataSource
    ingestion_run_id: int | None = None
    items: list[LineItem]


class StopResponse(TransitSchema):
    data_source: DataSource
    ingestion_run_id: int | None = None
    stop: StopItem


class StopLinesResponse(TransitSchema):
    data_source: DataSource
    ingestion_run_id: int | None = None
    stop: StopItem
    lines: list[LineItem]
    unresolved_summaries: list[UnresolvedLineSummary] = Field(default_factory=list)
    partial: bool


class LineResponse(TransitSchema):
    data_source: DataSource
    ingestion_run_id: int | None = None
    line: LineItem


class LineStopsResponse(TransitSchema):
    data_source: DataSource
    ingestion_run_id: int | None = None
    line: LineItem
    stops: list[LineStopItem]


class LineMapResponse(TransitSchema):
    data_source: DataSource
    ingestion_run_id: int | None = None
    line: LineItem
    start_stop_name: str | None
    end_stop_name: str | None
    geojson: dict[str, Any]


class ErrorBody(BaseModel):
    code: str
    message: str
