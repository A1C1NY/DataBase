"""线路、站点和站序模型。

TODO: 实现 lines、stops、line_routes。方向仅允许 0/1；外部 ID 可空且保留字符串；
市政府 stopId 只放 line_routes.shanghai_stop_id；(line_id, stop_id) 不设唯一以兼容环线。
线路/站点使用 is_active 逻辑停用，历史引用一律 RESTRICT。
"""

from app.db.base import Base


class Line(Base):
    # TODO: 补齐主键和字段后删除 __abstract__。
    __abstract__ = True
    __tablename__ = "lines"


class Stop(Base):
    # TODO: 补齐主键和字段后删除 __abstract__。
    __abstract__ = True
    __tablename__ = "stops"


class LineRoute(Base):
    # TODO: 补齐主键和字段后删除 __abstract__。
    __abstract__ = True
    __tablename__ = "line_routes"
