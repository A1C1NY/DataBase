from sqlalchemy.orm import DeclarativeBase, mapped_column 
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped
from datetime import datetime
from sqlalchemy import func, MetaData

BIGINT_UNSIGNED = BIGINT(unsigned=True)

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

class TimestampMixin:
    """带 created_at/updated_at 的基础表 mixin。"""

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False
    )




