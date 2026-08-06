"""Environment-backed application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings loaded from environment variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TRANSIT_",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False

    database_url: str

    jwt_secret: SecretStr = Field(min_length=32)
    jwt_expire_minutes: int = Field(default=30, ge=5, le=1440)

    amap_api_url: AnyHttpUrl = AnyHttpUrl("https://restapi.amap.com/")
    amap_api_key: SecretStr | None = None
    upstream_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    amap_min_request_interval_seconds: float = Field(default=1.0, ge=0.0, le=10.0)
    amap_line_id_min_request_interval_seconds: float = Field(
        default=0.04, ge=0.0, le=10.0
    )
    amap_rate_limit_retries: int = Field(default=3, ge=0, le=5)
    amap_rate_limit_backoff_seconds: float = Field(default=0.5, ge=0.0, le=10.0)
    city_code: str = Field(default="021", pattern=r"^[0-9]{3,6}$")

    cors_origins: list[AnyHttpUrl] = Field(
        default_factory=lambda: [AnyHttpUrl("http://localhost:5173")]
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("mysql+pymysql://"):
            raise ValueError("TRANSIT_DATABASE_URL 必须使用 mysql+pymysql 驱动")
        return value

    @field_validator("amap_api_key", mode="before")
    @classmethod
    def blank_amap_key_is_missing(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def production_cannot_enable_debug(self) -> "Settings":
        if self.app_env == "production" and self.debug:
            raise ValueError("production 环境不能启用 DEBUG")
        return self

    @property
    def cors_origin_strings(self) -> list[str]:
        """Return origins in the form expected by FastAPI CORSMiddleware."""

        return [str(origin).rstrip("/") for origin in self.cors_origins]

    def require_amap_api_key(self) -> str:
        """Return a usable Amap key or fail at the point of an upstream call."""

        if self.amap_api_key is None:
            raise RuntimeError("未配置 TRANSIT_AMAP_API_KEY")
        key = self.amap_api_key.get_secret_value().strip()
        if not key:
            raise RuntimeError("未配置 TRANSIT_AMAP_API_KEY")
        return key


@lru_cache
def get_settings() -> Settings:
    """Load and cache one Settings instance for the application process."""

    return Settings()  # type: ignore[call-arg]
