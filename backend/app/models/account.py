"""用户、收藏和查询日志模型。

TODO: 实现 users、favorite_stops、query_logs。用户删除时收藏 CASCADE、日志 user_id
SET NULL；站点引用 RESTRICT。username 唯一，日志建立 stop/time、user/time、time 索引。
"""

from app.db.base import Base
from datetime import datetime

from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BIGINT_UNSIGNED, TimestampMixin

class User(Base, TimestampMixin):
    """
    用户模型
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(ENUM('passenger','analyst','admin'), nullable=False, server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, server_default=func.current_timestamp(6))


class FavoriteStop(Base):
    # TODO: 补齐复合主键和字段后删除 __abstract__。
    __abstract__ = True
    __tablename__ = "favorite_stops"


class QueryLog(Base):
    # TODO: 补齐主键和字段后删除 __abstract__。
    __abstract__ = True
    __tablename__ = "query_logs"
