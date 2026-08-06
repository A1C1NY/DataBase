"""Tolerant Pydantic DTOs for Amap bus Web Service responses."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AmapDTO(BaseModel):
    model_config = ConfigDict(extra="allow")


def _string_or_none(value: Any) -> str | None:
    if value is None or value == "" or value == [] or value == {}:
        return None
    return str(value)


class AmapLineSummaryDTO(AmapDTO):
    id: str | None = None
    location: str | None = None
    name: str | None = None
    start_stop: str | None = None
    end_stop: str | None = None

    @field_validator("id", "start_stop", "end_stop", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> str | None:
        return _string_or_none(value)


class AmapBusStopDTO(AmapDTO):
    id: str | None = None
    name: str | None = None
    adcode: str | None = None
    citycode: str | None = None
    location: str | None = None
    sequence: str | None = None
    buslines: list[AmapLineSummaryDTO] = Field(default_factory=list)

    @field_validator("id", "adcode", "citycode", "sequence", mode="before")
    @classmethod
    def stringify_identifiers(cls, value: Any) -> str | None:
        return _string_or_none(value)


class AmapBusLineDTO(AmapDTO):
    id: str | None = None
    type: str | None = None
    name: str | None = None
    polyline: str | None = None
    citycode: str | None = None
    start_stop: str | None = None
    end_stop: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    loop: str | None = None
    status: str | None = None
    direc: str | None = None
    company: str | None = None
    distance: str | None = None
    basic_price: str | None = None
    total_price: str | None = None
    bounds: str | None = None
    uicolor: str | None = None
    busstops: list[AmapBusStopDTO] = Field(default_factory=list)

    @field_validator(
        "id",
        "citycode",
        "start_stop",
        "end_stop",
        "start_time",
        "end_time",
        "loop",
        "status",
        "direc",
        "distance",
        "basic_price",
        "total_price",
        "type",
        "name",
        "company",
        "bounds",
        "uicolor",
        mode="before",
    )
    @classmethod
    def normalize_scalar_strings(cls, value: Any) -> str | None:
        return _string_or_none(value)


class AmapStopResponseDTO(AmapDTO):
    status: str | None = None
    info: str | None = None
    infocode: str | None = None
    count: str | None = None
    busstops: list[AmapBusStopDTO] = Field(default_factory=list)

    @field_validator("status", "infocode", "count", mode="before")
    @classmethod
    def stringify_response_scalars(cls, value: Any) -> str | None:
        return _string_or_none(value)


class AmapLineResponseDTO(AmapDTO):
    status: str | None = None
    info: str | None = None
    infocode: str | None = None
    count: str | None = None
    buslines: list[AmapBusLineDTO] = Field(default_factory=list)

    @field_validator("status", "infocode", "count", mode="before")
    @classmethod
    def stringify_response_scalars(cls, value: Any) -> str | None:
        return _string_or_none(value)
