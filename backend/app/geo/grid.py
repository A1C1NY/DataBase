"""Meter-based grid aggregation helpers for analytics heatmaps."""

from dataclasses import dataclass
from math import cos, floor, hypot, isfinite, pi

EARTH_RADIUS_M = 6_371_008.8
LINE_SAMPLE_INTERVAL_M = 100.0
MAX_BBOX_AREA_KM2 = 100_000.0


@dataclass(frozen=True)
class BoundingBox:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    @property
    def reference_latitude(self) -> float:
        return (self.min_lat + self.max_lat) / 2.0

    def contains(self, longitude: float, latitude: float) -> bool:
        return (
            self.min_lon <= longitude <= self.max_lon
            and self.min_lat <= latitude <= self.max_lat
        )


def parse_bbox(value: str) -> BoundingBox:
    """
    处理 bbox 字符串并返回 BoundingBox 对象。
    Parameters:
        value (str): bbox 字符串，格式为 "min_lon,min_lat,max_lon,max_lat"。
    Returns:
        BoundingBox: 解析后的 BoundingBox 对象。
    Raises:
        ValueError: 如果 bbox 字符串格式不正确或包含无效的坐标。
    """

    try:
        values = [float(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise ValueError("bbox 必须包含 4 个数字") from exc
    if len(values) != 4:
        raise ValueError("bbox 必须按 min_lon,min_lat,max_lon,max_lat 填写")
    min_lon, min_lat, max_lon, max_lat = values
    if not all(isfinite(item) for item in values):
        raise ValueError("bbox 坐标必须是有限数字")
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
        raise ValueError("bbox 经度必须位于 -180 到 180")
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise ValueError("bbox 纬度必须位于 -90 到 90")
    if min_lon >= max_lon or min_lat >= max_lat:
        raise ValueError("bbox 最小坐标必须小于最大坐标")
    bbox = BoundingBox(min_lon, min_lat, max_lon, max_lat)
    if bbox_area_km2(bbox) > MAX_BBOX_AREA_KM2:
        raise ValueError(f"bbox 范围过大，不得超过 {MAX_BBOX_AREA_KM2:.0f} 平方公里")
    return bbox


def _meters_per_degree_longitude(reference_latitude: float) -> float:
    """
    计算在给定参考纬度下，每度经度对应的米数。
    Parameters:
        reference_latitude (float): 参考纬度（以度为单位）。
    Returns:
        float: 每度经度对应的米数。
    """
    return pi * EARTH_RADIUS_M / 180.0 * cos(reference_latitude * pi / 180.0)


def project(longitude: float, latitude: float, reference_latitude: float) -> tuple[float, float]:
    """
    将经纬度坐标投影到以米为单位的平面坐标系中。
    Parameters:
        longitude (float): 经度坐标。
        latitude (float): 纬度坐标。
        reference_latitude (float): 用于计算经度缩放的参考纬度。
    Returns:
        tuple[float, float]: 对应的平面坐标系中的 (x, y) 坐标（以米为单位）。
    """
    return (
        longitude * _meters_per_degree_longitude(reference_latitude),
        latitude * pi * EARTH_RADIUS_M / 180.0,
    )


def unproject(x: float, y: float, reference_latitude: float) -> tuple[float, float]:
    """
    将平面坐标系中的米坐标转换回经纬度坐标。

    Parameters:
        x (float): 平面坐标系中的 x 坐标（以米为单位）。
        y (float): 平面坐标系中的 y 坐标（以米为单位）。
        reference_latitude (float): 用于计算经度缩放的参考纬度。
    Returns:
        tuple[float, float]: 对应的经纬度坐标 (longitude, latitude)。
    """
    return (
        x / _meters_per_degree_longitude(reference_latitude),
        y / (pi * EARTH_RADIUS_M / 180.0),
    )


def bbox_area_km2(bbox: BoundingBox) -> float:
    """
    计算 BoundingBox 的面积（以平方公里为单位）。
    Parameters:
        bbox (BoundingBox): 要计算面积的边界框。
    Returns:
        float: 边界框的面积（以平方公里为单位）。
    """
    min_x, min_y = project(bbox.min_lon, bbox.min_lat, bbox.reference_latitude)
    max_x, max_y = project(bbox.max_lon, bbox.max_lat, bbox.reference_latitude)
    return (max_x - min_x) * (max_y - min_y) / 1_000_000.0


GridKey = tuple[int, int]


def grid_key(longitude: float, latitude: float, grid_size_m: int, reference_latitude: float) -> GridKey:
    """
    通过向下取整将经纬度坐标映射到网格单元的键。
    Parameters:
        longitude (float): 经度坐标。
        latitude (float): 纬度坐标。
        grid_size_m (int): 网格单元的大小（以米为单位）。
        reference_latitude (float): 用于计算经度缩放的参考纬度。
    Returns:
        GridKey: 对应的网格单元键 (x_index, y_index)。
    """
    x, y = project(longitude, latitude, reference_latitude)
    return floor(x / grid_size_m), floor(y / grid_size_m)


def grid_center(key: GridKey, grid_size_m: int, reference_latitude: float) -> tuple[float, float]:
    """
    计算网格单元的中心坐标。
    Parameters:
        key (GridKey): 网格单元键 (x_index, y_index)。
        grid_size_m (int): 网格单元的大小（以米为单位）。
        reference_latitude (float): 用于计算经度缩放的参考纬度。
    Returns:
        tuple[float, float]: 网格单元的中心坐标 (longitude, latitude)。
    """
    x = (key[0] + 0.5) * grid_size_m
    y = (key[1] + 0.5) * grid_size_m
    return unproject(x, y, reference_latitude)


def sample_segment(
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    reference_latitude: float,
    interval_m: float = LINE_SAMPLE_INTERVAL_M,
) -> list[tuple[float, float]]:
    """Return endpoints plus approximately equally spaced points along a segment."""

    start_x, start_y = project(*start, reference_latitude)
    end_x, end_y = project(*end, reference_latitude)
    distance = hypot(end_x - start_x, end_y - start_y)
    steps = max(1, int(distance / interval_m + 0.999999))
    return [
        (
            start[0] + (end[0] - start[0]) * index / steps,
            start[1] + (end[1] - start[1]) * index / steps,
        )
        for index in range(steps + 1)
    ]
