"""Meter grid validation and line sampling tests."""

from itertools import pairwise

import pytest

from app.geo.grid import grid_center, grid_key, parse_bbox, project, sample_segment


def test_bbox_parser_accepts_city_scale_bounds() -> None:
    bbox = parse_bbox("121.0,30.8,122.0,31.6")

    assert bbox.min_lon == 121.0
    assert bbox.max_lat == 31.6
    assert bbox.contains(121.5, 31.2)


@pytest.mark.parametrize(
    "value",
    [
        "121,31,120,32",
        "121,32,122,31",
        "121,31,122",
        "not-a-bbox",
        "nan,31,122,32",
        "-170,-80,170,80",
    ],
)
def test_bbox_parser_rejects_invalid_or_oversized_ranges(value: str) -> None:
    with pytest.raises(ValueError):
        parse_bbox(value)


def test_grid_center_round_trips_to_the_same_key() -> None:
    key = grid_key(121.4979, 31.2814, 300, 31.2)
    center = grid_center(key, 300, 31.2)

    assert grid_key(*center, 300, 31.2) == key


def test_segment_is_sampled_at_no_more_than_about_100_meters() -> None:
    points = sample_segment((121.0, 31.0), (121.01, 31.0), reference_latitude=31.0)

    assert len(points) > 2
    for start, end in pairwise(points):
        start_x, start_y = project(*start, 31.0)
        end_x, end_y = project(*end, 31.0)
        distance = ((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5
        assert distance <= 100.1
