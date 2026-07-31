"""异步数据库会话。

TODO: 配置 AsyncEngine 连接池、MySQL 会话时区 +08:00 和连接健康检查；提供请求级
AsyncSession 依赖。业务事务由 service 明确提交/回滚，repository 不擅自 commit。
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session

