"""用户、收藏和查询日志模型。

TODO: 实现 users、favorite_stops、query_logs。用户删除时收藏 CASCADE、日志 user_id
SET NULL；站点引用 RESTRICT。username 唯一，日志建立 stop/time、user/time、time 索引。
"""

from app.db.base import Base


class User(Base):
    # TODO: 补齐主键和字段后删除 __abstract__。
    __abstract__ = True
    __tablename__ = "users"


class FavoriteStop(Base):
    # TODO: 补齐复合主键和字段后删除 __abstract__。
    __abstract__ = True
    __tablename__ = "favorite_stops"


class QueryLog(Base):
    # TODO: 补齐主键和字段后删除 __abstract__。
    __abstract__ = True
    __tablename__ = "query_logs"
