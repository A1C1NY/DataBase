import pytest

from app.geo.coord import gcj02_to_wgs84, is_outside_china
from app.geo.geojson import feature_collection, line_feature, point_feature


def test_shanghai_gcj02_coordinate_is_shifted_to_wgs84() -> None:
    longitude, latitude = gcj02_to_wgs84(121.510610, 31.153278)

    assert longitude == pytest.approx(121.506, abs=0.002)
    assert latitude == pytest.approx(31.155, abs=0.002)


def test_coordinate_outside_china_is_not_modified() -> None:
    assert is_outside_china(-0.1276, 51.5072) is True
    assert gcj02_to_wgs84(-0.1276, 51.5072) == (-0.1276, 51.5072)


def test_invalid_coordinate_is_rejected() -> None:
    with pytest.raises(ValueError, match="经度"):
        gcj02_to_wgs84(181, 31)


def test_geojson_helpers_keep_longitude_before_latitude() -> None:
    line = line_feature([(121.1, 31.1), (121.2, 31.2)], properties={"line_id": 1})
    stop = point_feature(121.1, 31.1, properties={"stop_id": 2})
    collection = feature_collection([line, stop], metadata={"converted": True})

    assert line["geometry"]["coordinates"][0] == [121.1, 31.1]
    assert stop["geometry"]["coordinates"] == [121.1, 31.1]
    assert collection["metadata"] == {"converted": True}

