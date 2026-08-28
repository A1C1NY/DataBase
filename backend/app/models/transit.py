"""Amap bus stop, directional line, ordered stop, and path point models."""

from datetime import datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import (
    DATETIME,
    DECIMAL,
    ENUM,
    INTEGER,
    MEDIUMTEXT,
    SMALLINT,
    TIME,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BIGINT_UNSIGNED, MYSQL_TABLE_OPTIONS, Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.account import FavoriteLine, FavoriteStop, LineViewEvent, StopViewEvent
    from app.models.ingestion import IngestionRun


class BusStop(TimestampMixin, Base):
    __tablename__ = "bus_stops"
    __table_args__ = (
        UniqueConstraint("amap_stop_id", name="uq_bus_stops_amap_stop_id"),
        Index("idx_bus_stops_name_active", "normalized_name", "is_active"),
        Index(
            "idx_bus_stops_city_name_active",
            "city_code",
            "normalized_name",
            "is_active",
        ),
        Index("idx_bus_stops_location", "longitude", "latitude"),
        CheckConstraint(
            "longitude BETWEEN -180 AND 180", name="longitude_range"
        ),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    amap_stop_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stop_name: Mapped[str] = mapped_column(String(150), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(150), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(DECIMAL(10, 7), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(DECIMAL(10, 7), nullable=False)
    coordinate_system: Mapped[str] = mapped_column(
        ENUM("GCJ02"), nullable=False, server_default=text("'GCJ02'")
    )
    city_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    line_membership_status: Mapped[str] = mapped_column(
        ENUM("unknown", "partial", "complete"),
        nullable=False,
        server_default=text("'unknown'"),
    )
    lines_checked_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
    unresolved_line_summaries: Mapped[list[dict[str, str | None]] | None] = mapped_column(
        JSON, nullable=True
    )
    last_ingestion_run_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "ingestion_runs.id",
            name="fk_bus_stops_last_ingestion_run_id_ingestion_runs",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("1")
    )

    line_stops: Mapped[list["BusLineStop"]] = relationship(back_populates="stop")
    favorite_stops: Mapped[list["FavoriteStop"]] = relationship(back_populates="stop")
    view_events: Mapped[list["StopViewEvent"]] = relationship(back_populates="stop")
    last_ingestion_run: Mapped["IngestionRun | None"] = relationship(
        back_populates="last_modified_stops"
    )


class BusLine(TimestampMixin, Base):
    __tablename__ = "bus_lines"
    __table_args__ = (
        UniqueConstraint("amap_line_id", name="uq_bus_lines_amap_line_id"),
        Index("idx_bus_lines_name_active", "line_name", "is_active"),
        Index("idx_bus_lines_city_name_active", "city_code", "line_name", "is_active"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    amap_line_id: Mapped[str] = mapped_column(String(64), nullable=False)
    amap_reverse_line_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    line_name: Mapped[str] = mapped_column(String(100), nullable=False)
    amap_name: Mapped[str] = mapped_column(String(255), nullable=False)
    amap_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    city_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    start_stop_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    end_stop_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    first_departure_time: Mapped[time | None] = mapped_column(TIME(), nullable=True)
    last_departure_time: Mapped[time | None] = mapped_column(TIME(), nullable=True)
    loop_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    amap_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    distance_km: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 3), nullable=True)
    basic_price: Mapped[Decimal | None] = mapped_column(DECIMAL(8, 2), nullable=True)
    total_price: Mapped[Decimal | None] = mapped_column(DECIMAL(8, 2), nullable=True)
    bounds_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ui_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    polyline_raw: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    last_ingestion_run_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "ingestion_runs.id",
            name="fk_bus_lines_last_ingestion_run_id_ingestion_runs",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("1")
    )

    line_stops: Mapped[list["BusLineStop"]] = relationship(
        back_populates="line", cascade="all, delete-orphan"
    )
    path_points: Mapped[list["BusLinePathPoint"]] = relationship(
        back_populates="line", cascade="all, delete-orphan"
    )
    favorite_lines: Mapped[list["FavoriteLine"]] = relationship(back_populates="line")
    view_events: Mapped[list["LineViewEvent"]] = relationship(back_populates="line")
    last_ingestion_run: Mapped["IngestionRun | None"] = relationship(
        back_populates="last_modified_lines"
    )


class BusLineStop(Base):
    __tablename__ = "bus_line_stops"
    __table_args__ = (
        UniqueConstraint("line_id", "sequence_no", name="uq_bus_line_stops_line_sequence"),
        Index("idx_bus_line_stops_stop", "stop_id"),
        Index("idx_bus_line_stops_line_stop", "line_id", "stop_id"),
        CheckConstraint("sequence_no >= 1", name="sequence_positive"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "bus_lines.id",
            name="fk_bus_line_stops_line_id_bus_lines",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    stop_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "bus_stops.id",
            name="fk_bus_line_stops_stop_id_bus_stops",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(SMALLINT(unsigned=True), nullable=False)
    amap_stop_id_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ingestion_run_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "ingestion_runs.id",
            name="fk_bus_line_stops_ingestion_run_id_ingestion_runs",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    line: Mapped[BusLine] = relationship(back_populates="line_stops")
    stop: Mapped[BusStop] = relationship(back_populates="line_stops")
    ingestion_run: Mapped["IngestionRun"] = relationship(back_populates="line_stops")


class BusLinePathPoint(Base):
    __tablename__ = "bus_line_path_points"
    __table_args__ = (
        UniqueConstraint(
            "line_id", "sequence_no", name="uq_bus_line_path_points_line_sequence"
        ),
        Index("idx_bus_line_path_points_line_sequence", "line_id", "sequence_no"),
        CheckConstraint("sequence_no >= 1", name="sequence_positive"),
        CheckConstraint(
            "longitude BETWEEN -180 AND 180", name="longitude_range"
        ),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "bus_lines.id",
            name="fk_bus_line_path_points_line_id_bus_lines",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(DECIMAL(10, 7), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(DECIMAL(10, 7), nullable=False)
    coordinate_system: Mapped[str] = mapped_column(
        ENUM("GCJ02"), nullable=False, server_default=text("'GCJ02'")
    )
    ingestion_run_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "ingestion_runs.id",
            name="fk_bus_line_path_points_ingestion_run_id_ingestion_runs",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    line: Mapped[BusLine] = relationship(back_populates="path_points")
    ingestion_run: Mapped["IngestionRun"] = relationship(back_populates="path_points")
