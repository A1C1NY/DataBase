"""Alembic 环境入口。

TODO: 导入全部模型后生成首次迁移；人工核对 MySQL UNSIGNED、DATETIME(3)、
ENUM、CHECK、DESC 索引和外键删除策略，不能只接受自动生成结果。
"""

from logging.config import fileConfig

from alembic import context

from app.core.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401  # 确保模型注册进 metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # TODO: Alembic 使用同步 MySQL 驱动，或按官方 async 模板创建连接后 run_sync。
    raise NotImplementedError("请先配置 Alembic 的 MySQL 在线迁移连接")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

