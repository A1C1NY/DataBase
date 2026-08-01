"""Transit line, stop, and ordered route database models."""

from datetime import time
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DECIMAL, SMALLINT, TIME, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BIGINT_UNSIGNED, MYSQL_TABLE_OPTIONS, Base, TimestampMixin


class Line(TimestampMixin, Base):
    __tablename__ = "lines"
    __table_args__ = (
        UniqueConstraint("amap_line_id", name="uq_lines_amap_id"),
        UniqueConstraint("shanghai_line_id", "direction", name="uq_lines_shanghai_direction"),
        Index("idx_lines_name_active", "line_name", "is_active"),
        CheckConstraint("direction IN (0, 1)", name="chk_lines_direction"),
        CheckConstraint("line_type IS NULL OR line_type IN (1, 2, 3)", name="chk_lines_type"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    line_name: Mapped[str] = mapped_column(String(100), nullable=False)
    direction: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False)
    line_type: Mapped[int | None] = mapped_column(TINYINT(unsigned=True), nullable=True)
    shanghai_line_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amap_line_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    first_departure_time: Mapped[time | None] = mapped_column(TIME(), nullable=True)
    last_departure_time: Mapped[time | None] = mapped_column(TIME(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))

    routes: Mapped[list["LineRoute"]] = relationship(back_populates="line")
    arrival_infos: Mapped[list["ArrivalInfo"]] = relationship(back_populates="line")
    dispatch_schedules: Mapped[list["DispatchSchedule"]] = relationship(back_populates="line")


class Stop(TimestampMixin, Base):
    __tablename__ = "stops"
    __table_args__ = (
        UniqueConstraint("amap_stop_id", name="uq_stops_amap_id"),
        Index("idx_stops_location", "longitude", "latitude"),
        Index("idx_stops_name_active", "stop_name", "is_active"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="chk_stops_longitude"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="chk_stops_latitude"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    stop_name: Mapped[str] = mapped_column(String(150), nullable=False)
    amap_stop_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    longitude: Mapped[Decimal] = mapped_column(DECIMAL(10, 7), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(DECIMAL(10, 7), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))

    routes: Mapped[list["LineRoute"]] = relationship(back_populates="stop")
    favorite_stops: Mapped[list["FavoriteStop"]] = relationship(back_populates="stop")
    query_logs: Mapped[list["QueryLog"]] = relationship(back_populates="stop")
    arrival_infos: Mapped[list["ArrivalInfo"]] = relationship(back_populates="stop")


class LineRoute(Base):
    __tablename__ = "line_routes"
    __table_args__ = (
        UniqueConstraint("line_id", "sequence_no", name="uq_line_routes_line_sequence"),
        UniqueConstraint("line_id", "shanghai_stop_id", name="uq_line_routes_shanghai_stop"),
        Index("idx_line_routes_stop", "stop_id"),
        Index("idx_line_routes_line_stop", "line_id", "stop_id"),
        CheckConstraint("sequence_no >= 1", name="chk_line_routes_sequence"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "lines.id",
            name="fk_line_routes_line",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    stop_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "stops.id",
            name="fk_line_routes_stop",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(SMALLINT(unsigned=True), nullable=False)
    shanghai_stop_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    line: Mapped[Line] = relationship(back_populates="routes")
    stop: Mapped[Stop] = relationship(back_populates="routes")


from app.models.account import FavoriteStop, QueryLog  # noqa: E402
from app.models.ingestion import ArrivalInfo, DispatchSchedule  # noqa: E402
