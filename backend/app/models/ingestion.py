"""Amap ingestion run audit model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Index, String, Text, text
from sqlalchemy.dialects.mysql import DATETIME, ENUM, INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BIGINT_UNSIGNED, MYSQL_TABLE_OPTIONS, Base

if TYPE_CHECKING:
    from app.models.transit import BusLine, BusLinePathPoint, BusLineStop, BusStop


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("idx_ingestion_runs_status_started", "status", "started_at"),
        Index("idx_ingestion_runs_endpoint_started", "endpoint", "started_at"),
        Index("idx_ingestion_runs_started", "started_at"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(ENUM("stopname", "linename"), nullable=False)
    trigger_type: Mapped[str] = mapped_column(
        ENUM("sample_import", "manual", "user_request"), nullable=False
    )
    request_keyword: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
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

    last_modified_stops: Mapped[list["BusStop"]] = relationship(
        back_populates="last_ingestion_run"
    )
    last_modified_lines: Mapped[list["BusLine"]] = relationship(
        back_populates="last_ingestion_run"
    )
    line_stops: Mapped[list["BusLineStop"]] = relationship(back_populates="ingestion_run")
    path_points: Mapped[list["BusLinePathPoint"]] = relationship(
        back_populates="ingestion_run"
    )
