import httpx
import pytest

from app.core.config import Settings
from app.integrations.amap.client import AmapClient, AmapClientError


def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="mysql+pymysql://user:password@127.0.0.1/test",
        jwt_secret="test-secret-with-at-least-32-characters",
        amap_api_key="test-amap-key",
    )


def test_line_query_sends_extensions_all_without_exposing_key() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, json={"status": "1", "count": "0", "buslines": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        response = AmapClient(settings(), http_client).query_line(keywords="980路", city="021")

    assert response.buslines == []
    assert captured["extensions"] == "all"
    assert captured["key"] == "test-amap-key"


def test_stop_query_does_not_send_line_extension() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, json={"status": "1", "count": "0", "busstops": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        AmapClient(settings(), http_client).query_stop(keywords="云台路", city="021")

    assert "extensions" not in captured


def test_client_classifies_business_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"}
        )
    )

    with (
        httpx.Client(transport=transport) as http_client,
        pytest.raises(AmapClientError) as error,
    ):
        AmapClient(settings(), http_client).query_stop(keywords="云台路", city="021")

    assert error.value.kind == "business_error"


def test_client_rejects_blank_keyword_before_http() -> None:
    with pytest.raises(AmapClientError) as error:
        AmapClient(settings()).query_stop(keywords=" ", city="021")

    assert error.value.kind == "invalid_request"


def test_client_classifies_missing_api_key_as_configuration_error() -> None:
    missing_key_settings = Settings(
        _env_file=None,
        database_url="mysql+pymysql://user:password@127.0.0.1/test",
        jwt_secret="test-secret-with-at-least-32-characters",
        amap_api_key=None,
    )

    with pytest.raises(AmapClientError) as error:
        AmapClient(missing_key_settings).query_stop(keywords="云台路", city="021")

    assert error.value.kind == "configuration"
