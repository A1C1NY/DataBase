"""Read-only heatmap and stop detail view analytics."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from itertools import pairwise

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.core.time import SHANGHAI_TZ, to_mysql_datetime
from app.geo.coord import gcj02_to_wgs84
from app.geo.geojson import feature_collection, point_feature
from app.geo.grid import BoundingBox, grid_center, grid_key, sample_segment
from app.models.account import StopViewEvent
from app.models.transit import BusLine, BusLinePathPoint, BusStop
from app.schemas.analytics import (
    ActorScope,
    DistributionBucket,
    DistributionItem,
    HeatmapMetric,
    HeatmapResponse,
    StopPopularityItem,
    StopPopularityResponse,
    StopViewDistributionResponse,
)


def normalize_range(start_at: datetime, end_at: datetime) -> tuple[datetime, datetime]:
    """Interpret naive values as Shanghai time and return naive MySQL boundaries."""

    def localize(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=SHANGHAI_TZ)
        return value.astimezone(SHANGHAI_TZ)

    start = localize(start_at)
    end = localize(end_at)
    if start >= end:
        raise ValueError("end_at 必须晚于 start_at")
    return to_mysql_datetime(start), to_mysql_datetime(end)


class AnalyticsService:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _heatmap_response(
        counts: dict[tuple[int, int], set[int]],
        *,
        bbox: BoundingBox,
        grid_size_m: int,
        metric: HeatmapMetric,
    ) -> HeatmapResponse:
        features = []
        for key in sorted(counts):
            longitude, latitude = grid_center(key, grid_size_m, bbox.reference_latitude)
            longitude, latitude = gcj02_to_wgs84(longitude, latitude)
            features.append(
                point_feature(
                    longitude,
                    latitude,
                    properties={
                        "metric": metric,
                        "weight": len(counts[key]),
                        "grid_size_m": grid_size_m,
                    },
                )
            )
        geojson = feature_collection(
            features,
            metadata={
                "source_coordinate_system": "GCJ02",
                "coordinate_system": "WGS84",
                "converted": True,
                "bbox": [bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat],
            },
        )
        return HeatmapResponse(metric=metric, grid_size_m=grid_size_m, geojson=geojson)

    def stop_heatmap(self, bbox: BoundingBox, grid_size_m: int) -> HeatmapResponse:
        rows = self.session.execute(
            select(BusStop.id, BusStop.longitude, BusStop.latitude).where(
                BusStop.is_active.is_(True),
                BusStop.longitude.between(bbox.min_lon, bbox.max_lon),
                BusStop.latitude.between(bbox.min_lat, bbox.max_lat),
            )
        )
        counts: dict[tuple[int, int], set[int]] = defaultdict(set)
        for stop_id, longitude, latitude in rows:
            key = grid_key(float(longitude), float(latitude), grid_size_m, bbox.reference_latitude)
            counts[key].add(stop_id)
        return self._heatmap_response(counts, bbox=bbox, grid_size_m=grid_size_m, metric="stop_density")

    def line_heatmap(self, bbox: BoundingBox, grid_size_m: int) -> HeatmapResponse:
        candidate_lines = (
            select(BusLinePathPoint.line_id)
            .join(BusLine, BusLine.id == BusLinePathPoint.line_id)
            .where(
                BusLine.is_active.is_(True),
                BusLinePathPoint.longitude.between(bbox.min_lon, bbox.max_lon),
                BusLinePathPoint.latitude.between(bbox.min_lat, bbox.max_lat),
            )
            .distinct()
        )
        rows = self.session.execute(
            select(
                BusLinePathPoint.line_id,
                BusLinePathPoint.sequence_no,
                BusLinePathPoint.longitude,
                BusLinePathPoint.latitude,
            )
            .where(BusLinePathPoint.line_id.in_(candidate_lines))
            .order_by(BusLinePathPoint.line_id, BusLinePathPoint.sequence_no)
        )
        paths: dict[int, list[tuple[float, float]]] = defaultdict(list)
        for line_id, _sequence_no, longitude, latitude in rows:
            paths[line_id].append((float(longitude), float(latitude)))

        counts: dict[tuple[int, int], set[int]] = defaultdict(set)
        for line_id, path in paths.items():
            samples: Iterable[tuple[float, float]]
            if len(path) == 1:
                samples = path
            else:
                samples = (
                    point
                    for start, end in pairwise(path)
                    for point in sample_segment(start, end, reference_latitude=bbox.reference_latitude)
                )
            for longitude, latitude in samples:
                if bbox.contains(longitude, latitude):
                    counts[grid_key(longitude, latitude, grid_size_m, bbox.reference_latitude)].add(line_id)
        return self._heatmap_response(counts, bbox=bbox, grid_size_m=grid_size_m, metric="line_density")

    def stop_popularity(
        self, start_at: datetime, end_at: datetime, limit: int
    ) -> StopPopularityResponse:
        start, end = normalize_range(start_at, end_at)
        rows = self.session.execute(
            select(
                BusStop.id,
                BusStop.stop_name,
                func.count(StopViewEvent.id),
                func.count(distinct(StopViewEvent.user_id)),
            )
            .join(StopViewEvent, StopViewEvent.stop_id == BusStop.id)
            .where(
                BusStop.is_active.is_(True),
                StopViewEvent.actor_role == "passenger",
                StopViewEvent.viewed_at >= start,
                StopViewEvent.viewed_at < end,
            )
            .group_by(BusStop.id, BusStop.stop_name)
            .order_by(func.count(StopViewEvent.id).desc(), BusStop.id)
            .limit(limit)
        )
        return StopPopularityResponse(
            items=[
                StopPopularityItem(
                    stop_id=stop_id,
                    stop_name=stop_name,
                    detail_view_count=view_count,
                    unique_user_count=unique_users,
                )
                for stop_id, stop_name, view_count, unique_users in rows
            ]
        )

    def stop_view_distribution(
        self,
        stop_id: int,
        start_at: datetime,
        end_at: datetime,
        bucket: DistributionBucket,
        actor_scope: ActorScope,
    ) -> StopViewDistributionResponse | None:
        stop = self.session.scalar(
            select(BusStop).where(BusStop.id == stop_id, BusStop.is_active.is_(True))
        )
        if stop is None:
            return None
        start, end = normalize_range(start_at, end_at)
        statement = select(StopViewEvent.viewed_at).where(
            StopViewEvent.stop_id == stop_id,
            StopViewEvent.viewed_at >= start,
            StopViewEvent.viewed_at < end,
        )
        if actor_scope == "passenger":
            statement = statement.where(StopViewEvent.actor_role == "passenger")
        viewed_times = list(self.session.scalars(statement))
        items = _distribution_items(viewed_times, start, end, bucket)
        return StopViewDistributionResponse(
            stop_id=stop.id,
            stop_name=stop.stop_name,
            bucket=bucket,
            actor_scope=actor_scope,
            items=items,
        )


def _distribution_items(
    viewed_times: Iterable[datetime],
    start_at: datetime,
    end_at: datetime,
    bucket: DistributionBucket,
) -> list[DistributionItem]:
    values = list(viewed_times)
    if bucket == "hour":
        hour_counts = {hour: 0 for hour in range(24)}
        for viewed_at in values:
            hour_counts[viewed_at.hour] += 1
        return [
            DistributionItem(bucket=hour, detail_view_count=hour_counts[hour])
            for hour in range(24)
        ]
    if bucket == "weekday_hour":
        weekday_counts = {
            (weekday, hour): 0 for weekday in range(7) for hour in range(24)
        }
        for viewed_at in values:
            weekday_counts[(viewed_at.weekday(), viewed_at.hour)] += 1
        return [
            DistributionItem(
                bucket=f"{weekday}-{hour:02d}",
                detail_view_count=weekday_counts[(weekday, hour)],
            )
            for weekday in range(7)
            for hour in range(24)
        ]

    first_day = start_at.date()
    last_day = (end_at - timedelta(microseconds=1)).date()
    counts_by_day: dict[date, int] = defaultdict(int)
    for viewed_at in values:
        counts_by_day[viewed_at.date()] += 1
    result = []
    current = first_day
    while current <= last_day:
        result.append(DistributionItem(bucket=current, detail_view_count=counts_by_day[current]))
        current += timedelta(days=1)
    return result
