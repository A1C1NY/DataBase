"""配置模块单元测试。

这些测试对应课程简化版的配置职责：读取环境变量、校验数值范围和缓存 Settings。
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def make_settings(**overrides: object) -> Settings:
    """构造不读取项目 .env 的测试配置。"""
    values: dict[str, object] = {
        "database_url": "mysql+pymysql://user:password@127.0.0.1:3306/transit_system",
        "jwt_secret": "test-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_settings_use_expected_defaults() -> None:
    settings = make_settings()

    assert settings.app_env == "development"
    assert settings.app_debug is True
    assert settings.jwt_expire_minutes == 30
    assert settings.amap_api_url == "https://restapi.amap.com"
    assert settings.amap_api_key is None
    assert settings.shanghai_api_url is None
    assert settings.shanghai_api_key is None
    assert settings.upstream_timeout_seconds == 10.0


def test_secret_value_is_loaded_as_secret_str() -> None:
    settings = make_settings(jwt_secret="a-test-jwt-secret")

    assert settings.jwt_secret.get_secret_value() == "a-test-jwt-secret"
    assert "a-test-jwt-secret" not in repr(settings)


def test_jwt_expire_minutes_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        make_settings(jwt_expire_minutes=0)

    with pytest.raises(ValidationError):
        make_settings(jwt_expire_minutes=-1)


def test_jwt_expire_minutes_has_maximum() -> None:
    with pytest.raises(ValidationError):
        make_settings(jwt_expire_minutes=1441)


@pytest.mark.parametrize("value", [0, -1, 60.1])
def test_upstream_timeout_has_valid_range(value: float) -> None:
    with pytest.raises(ValidationError):
        make_settings(upstream_timeout_seconds=value)


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://user:password@localhost/transit_system")
    monkeypatch.setenv("JWT_SECRET", "cached-test-secret")

    first = get_settings()
    second = get_settings()

    assert first is second
    assert first.jwt_secret.get_secret_value() == "cached-test-secret"

    get_settings.cache_clear()
