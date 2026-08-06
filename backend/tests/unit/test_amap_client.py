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
        amap_min_request_interval_seconds=0,
        amap_line_id_min_request_interval_seconds=0,
        amap_rate_limit_backoff_seconds=0,
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


def test_line_id_query_uses_dedicated_endpoint_and_id_parameter() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured.update(dict(request.url.params))
        return httpx.Response(200, json={"status": "1", "buslines": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        response = AmapClient(settings(), http_client).query_line_by_id(
            amap_line_id="310100015143"
        )

    assert response.buslines == []
    assert captured["path"] == "/v3/bus/lineid"
    assert captured["id"] == "310100015143"
    assert captured["extensions"] == "all"
    assert "keywords" not in captured
    assert "city" not in captured


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
    assert error.value.infocode == "10001"


def test_client_retries_rate_limit_with_exponential_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(
                200,
                json={
                    "status": "0",
                    "info": "CUQPS_HAS_EXCEEDED_THE_LIMIT",
                    "infocode": "10021",
                },
            )
        return httpx.Response(200, json={"status": "1", "buslines": []})

    retry_settings = settings().model_copy(
        update={"amap_rate_limit_retries": 2, "amap_rate_limit_backoff_seconds": 0.25}
    )
    monkeypatch.setattr("app.integrations.amap.client.sleep", sleeps.append)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        response = AmapClient(retry_settings, http_client).query_line(
            keywords="980路", city="021"
        )

    assert response.buslines == []
    assert attempts == 3
    assert sleeps == [0.25, 0.5]


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
