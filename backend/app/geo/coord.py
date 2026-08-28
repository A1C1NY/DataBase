"""GCJ-02 coordinate validation and conversion utilities."""

from math import cos, pi, sin, sqrt

_A = 6378245.0
_EE = 0.00669342162296594323


def _validate(longitude: float, latitude: float) -> None:
    if not -180 <= longitude <= 180:
        raise ValueError("经度必须位于 -180 到 180")
    if not -90 <= latitude <= 90:
        raise ValueError("纬度必须位于 -90 到 90")


def is_outside_china(longitude: float, latitude: float) -> bool:
    _validate(longitude, latitude)
    return not (72.004 <= longitude <= 137.8347 and 0.8293 <= latitude <= 55.8271)


def _transform_latitude(longitude: float, latitude: float) -> float:
    result = -100.0 + 2.0 * longitude + 3.0 * latitude
    result += 0.2 * latitude * latitude + 0.1 * longitude * latitude
    result += 0.2 * sqrt(abs(longitude))
    result += (20.0 * sin(6.0 * longitude * pi) + 20.0 * sin(2.0 * longitude * pi)) * 2.0 / 3.0
    result += (20.0 * sin(latitude * pi) + 40.0 * sin(latitude / 3.0 * pi)) * 2.0 / 3.0
    return result + (
        160.0 * sin(latitude / 12.0 * pi) + 320 * sin(latitude * pi / 30.0)
    ) * 2.0 / 3.0


def _transform_longitude(longitude: float, latitude: float) -> float:
    result = 300.0 + longitude + 2.0 * latitude
    result += 0.1 * longitude * longitude + 0.1 * longitude * latitude
    result += 0.1 * sqrt(abs(longitude))
    result += (20.0 * sin(6.0 * longitude * pi) + 20.0 * sin(2.0 * longitude * pi)) * 2.0 / 3.0
    result += (20.0 * sin(longitude * pi) + 40.0 * sin(longitude / 3.0 * pi)) * 2.0 / 3.0
    return result + (
        150.0 * sin(longitude / 12.0 * pi) + 300.0 * sin(longitude / 30.0 * pi)
    ) * 2.0 / 3.0


def gcj02_to_wgs84(longitude: float, latitude: float) -> tuple[float, float]:
    """Convert a GCJ-02 point to an approximate WGS84 point.

    Coordinates outside mainland China's GCJ-02 coverage are returned unchanged.
    """

    _validate(longitude, latitude)
    if is_outside_china(longitude, latitude):
        return longitude, latitude

    delta_latitude = _transform_latitude(longitude - 105.0, latitude - 35.0)
    delta_longitude = _transform_longitude(longitude - 105.0, latitude - 35.0)
    rad_latitude = latitude / 180.0 * pi
    magic = sin(rad_latitude)
    magic = 1 - _EE * magic * magic
    sqrt_magic = sqrt(magic)
    delta_latitude = (
        delta_latitude * 180.0 / ((_A * (1 - _EE)) / (magic * sqrt_magic) * pi)
    )
    delta_longitude = (
        delta_longitude * 180.0 / (_A / sqrt_magic * cos(rad_latitude) * pi)
    )
    mapped_latitude = latitude + delta_latitude
    mapped_longitude = longitude + delta_longitude
    return longitude * 2 - mapped_longitude, latitude * 2 - mapped_latitude

