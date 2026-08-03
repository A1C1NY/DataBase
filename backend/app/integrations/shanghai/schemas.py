"""Pydantic DTOs for the Shanghai nearby-transit response."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ShanghaiDTO(BaseModel):
    model_config = ConfigDict(extra="allow")


class PointDTO(ShanghaiDTO):
    lon: str | int | float | None = None
    lat: str | int | float | None = None


class SaiDTO(ShanghaiDTO):
    nextBusDistance: str | int | None = None
    currentBusComfort: str | int | None = None
    currentBusStopCount: str | int | None = None
    nextBusStopCount: str | int | None = None
    currentBusArriveTime: str | int | None = None
    currentLicensePlate: str | None = None
    currentBarrierFree: bool | str | int | None = None
    nextBarrierFree: bool | str | int | None = None
    upDown: str | int | None = None
    nextBusArriveTime: str | int | None = None
    nextLicensePlate: str | None = None
    currentBusDistance: str | int | None = None


class DispatchCarDTO(ShanghaiDTO):
    countdown: str | None = None
    time: str | None = None
    vehicle: str | None = None


class DispatchScheduleDTO(ShanghaiDTO):
    scheduleMsgDefault: str | None = None
    dispatchCars: list[DispatchCarDTO] = Field(default_factory=list)
    lineId: str | None = None
    lineName: str | None = None
    scheduleCode: str | int | None = None
    scheduleMsgShort: str | None = None
    direction: str | int | None = None

    @field_validator("lineId", mode="before")
    @classmethod
    def stringify_id(cls, value: Any) -> str | None:
        return None if value is None or value == "" else str(value)


class NearbyTrafficLineStopDTO(ShanghaiDTO):
    lineId: str | None = None
    lineName: str | None = None
    stopId: str | None = None
    stopName: str | None = None
    startStopName: str | None = None
    endStopName: str | None = None
    upDown: str | int | None = None
    type: str | int | None = None
    point: PointDTO | None = None
    startEarlyLateTime: str | None = None
    endEarlyLateTime: str | None = None
    sai: SaiDTO | None = None
    dispatchCarSchedule: DispatchScheduleDTO | None = None

    @field_validator("lineId", "stopId", mode="before")
    @classmethod
    def stringify_ids(cls, value: Any) -> str | None:
        return None if value is None or value == "" else str(value)


class ShanghaiNearbyResponse(ShanghaiDTO):
    nearByTrafficLineStop: list[NearbyTrafficLineStopDTO] = Field(default_factory=list)
    retCode: str | int | None = None


# Short names are convenient for clients and preserve compatibility with likely callers.
ShanghaiResponse = ShanghaiNearbyResponse
ShanghaiStop = NearbyTrafficLineStopDTO
ShanghaiSai = SaiDTO
ShanghaiDispatchSchedule = DispatchScheduleDTO
ShanghaiDispatchCar = DispatchCarDTO
