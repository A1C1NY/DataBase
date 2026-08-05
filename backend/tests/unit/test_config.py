from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings

VALID_DATABASE_URL = (
    "mysql+pymysql://transit_user:test_password@127.0.0.1:3306/"
    "amap_transit_test?charset=utf8mb4"
)
VALID_JWT_SECRET = "a-test-secret-with-at-least-32-characters"


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": VALID_DATABASE_URL,
        "jwt_secret": VALID_JWT_SECRET,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_defaults_match_project_contract() -> None:
    settings = make_settings()

    assert settings.app_env == "development"
    assert settings.debug is False
    assert settings.jwt_expire_minutes == 30
    assert settings.upstream_timeout_seconds == 10
    assert settings.city_code == "021"
    assert str(settings.amap_api_url) == "https://restapi.amap.com/"
    assert settings.cors_origin_strings == ["http://localhost:5173"]


@pytest.mark.parametrize("minutes", [4, 1441])
def test_jwt_expiration_has_safe_bounds(minutes: int) -> None:
    with pytest.raises(ValidationError):
        make_settings(jwt_expire_minutes=minutes)


def test_database_url_requires_pymysql() -> None:
    with pytest.raises(ValidationError, match=r"mysql\+pymysql"):
        make_settings(database_url="sqlite:///test.db")


def test_short_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(jwt_secret="too-short")


def test_blank_amap_key_is_optional_until_an_upstream_call() -> None:
    settings = make_settings(amap_api_key="  ")

    assert settings.amap_api_key is None
    with pytest.raises(RuntimeError, match="TRANSIT_AMAP_API_KEY"):
        settings.require_amap_api_key()


def test_require_amap_key_returns_secret_without_exposing_it_in_repr() -> None:
    settings = make_settings(amap_api_key="amap-test-key")

    assert settings.require_amap_api_key() == "amap-test-key"
    assert "amap-test-key" not in repr(settings)


def test_production_rejects_debug_mode() -> None:
    with pytest.raises(ValidationError, match="production"):
        make_settings(app_env="production", debug=True)


def test_get_settings_reads_environment_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSIT_DATABASE_URL", VALID_DATABASE_URL)
    monkeypatch.setenv("TRANSIT_JWT_SECRET", VALID_JWT_SECRET)

    first = get_settings()
    second = get_settings()

    assert first is second
