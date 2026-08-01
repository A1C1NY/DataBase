"""User, favorite-stop, and query-log database models."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.mysql import DATETIME, ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BIGINT_UNSIGNED, MYSQL_TABLE_OPTIONS, Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.transit import Stop


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = MYSQL_TABLE_OPTIONS

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        ENUM("passenger", "analyst", "admin"),
        nullable=False,
        server_default=text("'passenger'"),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))

    favorite_stops: Mapped[list["FavoriteStop"]] = relationship(
        back_populates="user", passive_deletes=True
    )
    query_logs: Mapped[list["QueryLog"]] = relationship(back_populates="user", passive_deletes=True)


class FavoriteStop(Base):
    __tablename__ = "favorite_stops"
    __table_args__ = (
        Index("idx_favorite_stops_stop", "stop_id"),
        MYSQL_TABLE_OPTIONS,
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "users.id",
            name="fk_favorite_stops_user",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    stop_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "stops.id",
            name="fk_favorite_stops_stop",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)")
    )

    user: Mapped[User] = relationship(back_populates="favorite_stops")
    stop: Mapped["Stop"] = relationship(back_populates="favorite_stops")


class QueryLog(Base):
    __tablename__ = "query_logs"
    __table_args__ = (
        Index("idx_query_logs_stop_time", "stop_id", "queried_at"),
        Index("idx_query_logs_user_time", "user_id", "queried_at"),
        Index("idx_query_logs_time", "queried_at"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", name="fk_query_logs_user", onupdate="RESTRICT", ondelete="SET NULL"),
        nullable=True,
    )
    stop_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("stops.id", name="fk_query_logs_stop", onupdate="RESTRICT", ondelete="RESTRICT"),
        nullable=False,
    )
    queried_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)")
    )

    user: Mapped[User | None] = relationship(back_populates="query_logs")
    stop: Mapped["Stop"] = relationship(back_populates="query_logs")
