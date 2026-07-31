"""同步数据库 Engine 和 Session 管理。"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()

# Engine 是应用级对象，管理数据库连接池。
# 整个应用只需要创建一次。
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

# SessionFactory 是 Session 的工厂，不是一个具体的数据库会话。
SessionFactory = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_session() -> Generator[Session, None, None]:
    """为一次请求提供数据库 Session，并在请求结束后关闭。"""

    session = SessionFactory()

    try:
        yield session
        
    finally:
        session.close()
