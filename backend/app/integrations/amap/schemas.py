"""Pydantic DTOs for the two supported Amap bus response shapes."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AmapDTO(BaseModel):
    model_config = ConfigDict(extra="allow")


class AmapBusLineSummary(AmapDTO):
    id: str | None = None
    name: str | None = None
    location: str | None = None
    start_stop: str | None = None
    end_stop: str | None = None

    @field_validator("id", mode="before")
    @classmethod
    def stringify_id(cls, value: Any) -> str | None:
        return None if value is None or value == "" else str(value)

    @field_validator("start_stop", "end_stop", mode="before")
    @classmethod
    def empty_collection_is_missing(cls, value: Any) -> Any:
        return None if value == [] or value == {} else value


class AmapBusStop(AmapDTO):
    id: str | None = None
    name: str | None = None
    location: str | None = None
    sequence: str | int | None = None
    buslines: list[AmapBusLineSummary] = Field(default_factory=list)

    @field_validator("id", mode="before")
    @classmethod
    def stringify_id(cls, value: Any) -> str | None:
        return None if value is None or value == "" else str(value)


class AmapBusLine(AmapBusLineSummary):
    start_time: str | None = None
    end_time: str | None = None
    direc: str | None = None
    busstops: list[AmapBusStop] = Field(default_factory=list)

    @field_validator("direc", mode="before")
    @classmethod
    def stringify_direction_id(cls, value: Any) -> str | None:
        return None if value is None or value == "" else str(value)


class AmapStopResponse(AmapDTO):
    status: str | int | None = None
    info: str | None = None
    infocode: str | int | None = None
    count: str | int | None = None
    busstops: list[AmapBusStop] = Field(default_factory=list)


class AmapLineResponse(AmapDTO):
    status: str | int | None = None
    info: str | None = None
    infocode: str | int | None = None
    count: str | int | None = None
    buslines: list[AmapBusLine] = Field(default_factory=list)
