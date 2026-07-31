"""SQLAlchemy 声明式基类。

TODO: 为需要 created_at/updated_at 的基础表增加可复用 mixin；所有 BIGINT 主键和外键
在 MySQL 中必须保持 UNSIGNED 类型一致。
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

