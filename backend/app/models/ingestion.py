"""Ingestion-run, arrival snapshot, and dispatch database models."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    desc,
    text,
)
from sqlalchemy.dialects.mysql import DATETIME, ENUM, INTEGER, SMALLINT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BIGINT_UNSIGNED, MYSQL_TABLE_OPTIONS, Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("idx_ingestion_runs_status_started", "status", "started_at"),
        Index("idx_ingestion_runs_source_task_started", "source", "task_type", "started_at"),
        Index("idx_ingestion_runs_started", "started_at"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(ENUM("shanghai", "amap"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_type: Mapped[str] = mapped_column(
        ENUM("scheduled", "manual", "user_request"), nullable=False
    )
    request_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
    status: Mapped[str] = mapped_column(
        ENUM("running", "success", "partial", "failed"),
        nullable=False,
        server_default=text("'running'"),
    )
    received_count: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, server_default=text("0")
    )
    inserted_count: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, server_default=text("0")
    )
    updated_count: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, server_default=text("0")
    )
    skipped_count: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, server_default=text("0")
    )
    failed_count: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, server_default=text("0")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    arrival_infos: Mapped[list["ArrivalInfo"]] = relationship(back_populates="ingestion_run")
    dispatch_schedules: Mapped[list["DispatchSchedule"]] = relationship(
        back_populates="ingestion_run"
    )


class ArrivalInfo(Base):
    __tablename__ = "arrival_infos"
    __table_args__ = (
        UniqueConstraint("ingestion_run_id", "line_id", "stop_id", name="uq_arrival_run_line_stop"),
        Index("idx_arrival_realtime", "line_id", "stop_id", "collected_at"),
        Index("idx_arrival_stop_time", "stop_id", desc("collected_at")),
        Index("idx_arrival_line_time", "line_id", "collected_at"),
        Index("idx_arrival_time", "collected_at"),
        CheckConstraint(
            "source_up_down IS NULL OR source_up_down IN (0, 1)",
            name="chk_arrival_source_direction",
        ),
        CheckConstraint(
            "current_bus_comfort IS NULL OR current_bus_comfort IN (0, 1, 2, 3)",
            name="chk_arrival_comfort",
        ),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    ingestion_run_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "ingestion_runs.id",
            name="fk_arrival_ingestion_run",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    line_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("lines.id", name="fk_arrival_line", onupdate="RESTRICT", ondelete="RESTRICT"),
        nullable=False,
    )
    stop_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("stops.id", name="fk_arrival_stop", onupdate="RESTRICT", ondelete="RESTRICT"),
        nullable=False,
    )
    source_up_down: Mapped[int | None] = mapped_column(TINYINT(unsigned=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    current_bus_distance_m: Mapped[int | None] = mapped_column(
        INTEGER(unsigned=True), nullable=True
    )
    current_bus_arrival_min: Mapped[int | None] = mapped_column(
        INTEGER(unsigned=True), nullable=True
    )
    current_bus_comfort: Mapped[int | None] = mapped_column(TINYINT(unsigned=True), nullable=True)
    current_bus_stop_count: Mapped[int | None] = mapped_column(
        SMALLINT(unsigned=True), nullable=True
    )
    current_license_plate: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_barrier_free: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    next_bus_distance_m: Mapped[int | None] = mapped_column(INTEGER(unsigned=True), nullable=True)
    next_bus_arrival_min: Mapped[int | None] = mapped_column(INTEGER(unsigned=True), nullable=True)
    next_bus_stop_count: Mapped[int | None] = mapped_column(SMALLINT(unsigned=True), nullable=True)
    next_license_plate: Mapped[str | None] = mapped_column(String(64), nullable=True)
    next_barrier_free: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    ingestion_run: Mapped[IngestionRun] = relationship(back_populates="arrival_infos")
    line: Mapped["Line"] = relationship(back_populates="arrival_infos")
    stop: Mapped["Stop"] = relationship(back_populates="arrival_infos")


class DispatchSchedule(Base):
    __tablename__ = "dispatch_schedules"
    __table_args__ = (
        UniqueConstraint("ingestion_run_id", "line_id", name="uq_dispatch_schedule_run_line"),
        Index("idx_dispatch_schedule_line_time", "line_id", "collected_at"),
        Index("idx_dispatch_schedule_time", "collected_at"),
        CheckConstraint(
            "schedule_code IS NULL OR schedule_code IN (-1, 0, 1)",
            name="chk_dispatch_schedule_code",
        ),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    ingestion_run_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "ingestion_runs.id",
            name="fk_dispatch_schedule_ingestion_run",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    line_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "lines.id",
            name="fk_dispatch_schedule_line",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    collected_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    schedule_code: Mapped[int | None] = mapped_column(SMALLINT(), nullable=True)
    message_default: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message_short: Mapped[str | None] = mapped_column(String(255), nullable=True)

    ingestion_run: Mapped[IngestionRun] = relationship(back_populates="dispatch_schedules")
    line: Mapped["Line"] = relationship(back_populates="dispatch_schedules")
    cars: Mapped[list["DispatchCar"]] = relationship(
        back_populates="schedule", passive_deletes=True
    )


class DispatchCar(Base):
    __tablename__ = "dispatch_cars"
    __table_args__ = (
        UniqueConstraint("schedule_id", "sequence_no", name="uq_dispatch_cars_schedule_sequence"),
        Index("idx_dispatch_cars_departure", "planned_departure_at"),
        CheckConstraint("sequence_no >= 1", name="chk_dispatch_cars_sequence"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "dispatch_schedules.id",
            name="fk_dispatch_cars_schedule",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False)
    vehicle_text: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_barrier_free: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    planned_departure_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
    countdown_text: Mapped[str | None] = mapped_column(String(64), nullable=True)
    countdown_seconds: Mapped[int | None] = mapped_column(INTEGER(unsigned=True), nullable=True)

    schedule: Mapped[DispatchSchedule] = relationship(back_populates="cars")


from app.models.transit import Line, Stop  # noqa: E402
