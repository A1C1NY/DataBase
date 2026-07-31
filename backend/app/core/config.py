"""环境配置。

TODO: 根据真实上海接口补齐 URL/鉴权字段，并为生产环境校验弱 JWT 密钥、空 API 密钥
和不安全的数据库连接；不要给任何密钥提供可用于生产的默认值。
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_debug: bool = False
    database_url: str
    jwt_secret: SecretStr
    jwt_expire_minutes: int = 30
    amap_api_url: str = "https://restapi.amap.com"
    amap_api_key: SecretStr | None = None
    shanghai_api_url: str | None = None
    shanghai_api_key: SecretStr | None = None
    upstream_timeout_seconds: float = 10.0
    enable_scheduler: bool = False
    scheduled_seed_coordinates: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

