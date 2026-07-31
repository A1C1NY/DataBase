from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_debug: bool = True

    database_url: str
    jwt_secret: SecretStr
    jwt_expire_minutes: int = Field(default=30, ge=5, le=1440)

    amap_api_url: str = "https://restapi.amap.com"
    amap_api_key: SecretStr | None = None
    shanghai_api_url: str | None = None
    shanghai_api_key: SecretStr | None = None
    upstream_timeout_seconds: float = Field(default=10.0, gt=0, le=60)


@lru_cache
def get_settings() -> Settings:
    return Settings()
