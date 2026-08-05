"""Small GeoJSON constructors used by line and heatmap APIs."""

from collections.abc import Iterable, Mapping
from typing import Any

GeoJSON = dict[str, Any]


def point_feature(
    longitude: float,
    latitude: float,
    *,
    properties: Mapping[str, Any] | None = None,
) -> GeoJSON:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": dict(properties or {}),
    }


def line_feature(
    coordinates: Iterable[tuple[float, float]],
    *,
    properties: Mapping[str, Any] | None = None,
) -> GeoJSON:
    points = [[longitude, latitude] for longitude, latitude in coordinates]
    if len(points) < 2:
        raise ValueError("GeoJSON LineString 至少需要两个点")
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": points},
        "properties": dict(properties or {}),
    }


def feature_collection(
    features: Iterable[GeoJSON], *, metadata: Mapping[str, Any] | None = None
) -> GeoJSON:
    result: GeoJSON = {"type": "FeatureCollection", "features": list(features)}
    if metadata:
        result["metadata"] = dict(metadata)
    return result

