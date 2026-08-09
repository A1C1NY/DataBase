"""Read-only database queries and response construction for transit data."""

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.geo.coord import gcj02_to_wgs84
from app.geo.geojson import feature_collection, line_feature, point_feature
from app.integrations.amap.parser import normalize_name
from app.models.transit import BusLine, BusLinePathPoint, BusLineStop, BusStop
from app.schemas.transit import (
    DataSource,
    LineItem,
    LineMapResponse,
    LineResponse,
    LineStopItem,
    LineStopsResponse,
    StopItem,
    UnresolvedLineSummary,
)


class TransitService:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _active_stop_query() -> Select[tuple[BusStop]]:
        return select(BusStop).where(BusStop.is_active.is_(True))

    @staticmethod
    def _active_line_query() -> Select[tuple[BusLine]]:
        return select(BusLine).where(BusLine.is_active.is_(True))

    def search_stops(self, query: str, city_code: str, limit: int) -> list[BusStop]:
        normalized = normalize_name(query)
        if not normalized:
            return []
        statement = (
            self._active_stop_query()
            .where(
                BusStop.city_code == city_code,
                BusStop.normalized_name.contains(normalized),
            )
            .order_by(BusStop.normalized_name, BusStop.id)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def get_stop(self, stop_id: int) -> BusStop | None:
        return self.session.scalar(
            self._active_stop_query().where(BusStop.id == stop_id)
        )

    def get_stop_by_amap_id(self, amap_stop_id: str) -> BusStop | None:
        return self.session.scalar(
            self._active_stop_query().where(BusStop.amap_stop_id == amap_stop_id)
        )

    def get_lines_for_stop(self, stop_id: int) -> list[BusLine]:
        statement = (
            self._active_line_query()
            .join(BusLineStop, BusLineStop.line_id == BusLine.id)
            .where(BusLineStop.stop_id == stop_id)
            .distinct()
            .order_by(BusLine.line_name, BusLine.id)
        )
        return list(self.session.scalars(statement))

    @staticmethod
    def get_unresolved_lines_for_stop(stop: BusStop) -> list[UnresolvedLineSummary]:
        result: list[UnresolvedLineSummary] = []
        for item in stop.unresolved_line_summaries or []:
            try:
                result.append(UnresolvedLineSummary.model_validate(item))
            except (TypeError, ValueError):
                continue
        return result

    def get_line(self, line_id: int) -> BusLine | None:
        return self.session.scalar(
            self._active_line_query().where(BusLine.id == line_id)
        )

    def get_line_by_amap_id(self, amap_line_id: str) -> BusLine | None:
        return self.session.scalar(
            self._active_line_query().where(BusLine.amap_line_id == amap_line_id)
        )

    def search_lines(self, query: str, city_code: str, limit: int) -> list[BusLine]:
        keyword = query.strip()
        if not keyword:
            return []
        statement = (
            self._active_line_query()
            .where(
                BusLine.city_code == city_code,
                or_(
                    BusLine.line_name.contains(keyword),
                    BusLine.amap_name.contains(keyword),
                ),
            )
            .order_by(BusLine.line_name, BusLine.id)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def is_line_complete(self, line: BusLine) -> bool:
        if not line.polyline_raw.strip():
            return False
        stop_count = self.session.scalar(
            select(func.count()).select_from(BusLineStop).where(BusLineStop.line_id == line.id)
        )
        path_count = self.session.scalar(
            select(func.count())
            .select_from(BusLinePathPoint)
            .where(BusLinePathPoint.line_id == line.id)
        )
        return (stop_count or 0) >= 1 and (path_count or 0) >= 2

    def get_line_stops(self, line_id: int) -> list[BusLineStop]:
        statement = (
            select(BusLineStop)
            .options(joinedload(BusLineStop.stop))
            .join(BusStop, BusStop.id == BusLineStop.stop_id)
            .where(BusLineStop.line_id == line_id, BusStop.is_active.is_(True))
            .order_by(BusLineStop.sequence_no)
        )
        return list(self.session.scalars(statement))

    def get_line_path(self, line_id: int) -> list[BusLinePathPoint]:
        return list(
            self.session.scalars(
                select(BusLinePathPoint)
                .where(BusLinePathPoint.line_id == line_id)
                .order_by(BusLinePathPoint.sequence_no)
            )
        )

    @staticmethod
    def stop_item(stop: BusStop) -> StopItem:
        return StopItem.model_validate(stop)

    @staticmethod
    def line_item(line: BusLine) -> LineItem:
        return LineItem.model_validate(line)

    def line_response(
        self, line: BusLine, *, data_source: DataSource, ingestion_run_id: int | None = None
    ) -> LineResponse:
        return LineResponse(
            data_source=data_source,
            ingestion_run_id=ingestion_run_id,
            line=self.line_item(line),
        )

    def line_stops_response(
        self, line: BusLine, *, data_source: DataSource, ingestion_run_id: int | None = None
    ) -> LineStopsResponse:
        stops = self.get_line_stops(line.id)
        return LineStopsResponse(
            data_source=data_source,
            ingestion_run_id=ingestion_run_id,
            line=self.line_item(line),
            stops=[
                LineStopItem(sequence_no=item.sequence_no, stop=self.stop_item(item.stop))
                for item in stops
            ],
        )

    def line_map_response(
        self, line: BusLine, *, data_source: DataSource, ingestion_run_id: int | None = None
    ) -> LineMapResponse:
        path = self.get_line_path(line.id)
        stops = self.get_line_stops(line.id)
        path_coordinates = [
            gcj02_to_wgs84(float(point.longitude), float(point.latitude)) for point in path
        ]
        features = [
            line_feature(
                path_coordinates,
                properties={
                    "line_id": line.id,
                    "amap_line_id": line.amap_line_id,
                    "line_name": line.line_name,
                },
            )
        ]
        features.extend(
            point_feature(
                *gcj02_to_wgs84(float(item.stop.longitude), float(item.stop.latitude)),
                properties={
                    "stop_id": item.stop.id,
                    "amap_stop_id": item.stop.amap_stop_id,
                    "stop_name": item.stop.stop_name,
                    "sequence_no": item.sequence_no,
                },
            )
            for item in stops
        )
        geojson = feature_collection(
            features,
            metadata={
                "source_coordinate_system": "GCJ02",
                "coordinate_system": "WGS84",
                "converted": True,
            },
        )
        return LineMapResponse(
            data_source=data_source,
            ingestion_run_id=ingestion_run_id,
            line=self.line_item(line),
            start_stop_name=line.start_stop_name,
            end_stop_name=line.end_stop_name,
            geojson=geojson,
        )
