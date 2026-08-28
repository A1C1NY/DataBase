"""User, favorites, and stop detail view event models."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME, ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BIGINT_UNSIGNED, MYSQL_TABLE_OPTIONS, Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.transit import BusLine, BusStop


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        ENUM("passenger", "analyst", "admin"),
        nullable=False,
        server_default=text("'passenger'"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("1")
    )

    favorite_stops: Mapped[list["FavoriteStop"]] = relationship(
        back_populates="user", passive_deletes=True
    )
    favorite_lines: Mapped[list["FavoriteLine"]] = relationship(
        back_populates="user", passive_deletes=True
    )
    view_events: Mapped[list["StopViewEvent"]] = relationship(
        back_populates="user", passive_deletes=True
    )
    line_view_events: Mapped[list["LineViewEvent"]] = relationship(
        back_populates="user", passive_deletes=True
    )


class FavoriteStop(Base):
    __tablename__ = "favorite_stops"
    __table_args__ = (Index("idx_favorite_stops_stop", "stop_id"), MYSQL_TABLE_OPTIONS)

    user_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "users.id",
            name="fk_favorite_stops_user_id_users",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    stop_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "bus_stops.id",
            name="fk_favorite_stops_stop_id_bus_stops",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)")
    )

    user: Mapped[User] = relationship(back_populates="favorite_stops")
    stop: Mapped["BusStop"] = relationship(back_populates="favorite_stops")


class FavoriteLine(Base):
    __tablename__ = "favorite_lines"
    __table_args__ = (Index("idx_favorite_lines_line", "line_id"), MYSQL_TABLE_OPTIONS)

    user_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "users.id",
            name="fk_favorite_lines_user_id_users",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    line_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "bus_lines.id",
            name="fk_favorite_lines_line_id_bus_lines",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)")
    )

    user: Mapped[User] = relationship(back_populates="favorite_lines")
    line: Mapped["BusLine"] = relationship(back_populates="favorite_lines")


class StopViewEvent(Base):
    __tablename__ = "stop_view_events"
    __table_args__ = (
        Index("idx_stop_view_events_stop_time", "stop_id", "viewed_at"),
        Index("idx_stop_view_events_role_time", "actor_role", "viewed_at"),
        Index("idx_stop_view_events_time", "viewed_at"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "users.id",
            name="fk_stop_view_events_user_id_users",
            onupdate="RESTRICT",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    actor_role: Mapped[str] = mapped_column(
        ENUM("anonymous", "passenger", "analyst", "admin"), nullable=False
    )
    stop_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "bus_stops.id",
            name="fk_stop_view_events_stop_id_bus_stops",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    entry_point: Mapped[str] = mapped_column(
        ENUM("search", "line_map", "favorite", "direct"), nullable=False
    )
    viewed_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)")
    )

    user: Mapped[User | None] = relationship(back_populates="view_events")
    stop: Mapped["BusStop"] = relationship(back_populates="view_events")


class LineViewEvent(Base):
    """A successful bus-line detail view."""

    __tablename__ = "line_view_events"
    __table_args__ = (
        Index("idx_line_view_events_line_time", "line_id", "viewed_at"),
        Index("idx_line_view_events_role_time", "actor_role", "viewed_at"),
        Index("idx_line_view_events_time", "viewed_at"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", onupdate="RESTRICT", ondelete="SET NULL"),
        nullable=True,
    )
    actor_role: Mapped[str] = mapped_column(
        ENUM("anonymous", "passenger", "analyst", "admin"), nullable=False
    )
    line_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("bus_lines.id", onupdate="RESTRICT", ondelete="RESTRICT"),
        nullable=False,
    )
    entry_point: Mapped[str] = mapped_column(
        ENUM("search", "favorite", "direct"), nullable=False
    )
    viewed_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)")
    )

    user: Mapped[User | None] = relationship(back_populates="line_view_events")
    line: Mapped["BusLine"] = relationship(back_populates="view_events")
