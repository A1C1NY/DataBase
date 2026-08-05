"""Synchronous HTTPX client for Amap bus stop and line endpoints."""

from urllib.parse import urljoin

import httpx

from app.core.config import Settings, get_settings
from app.integrations.amap.schemas import AmapLineResponseDTO, AmapStopResponseDTO


class AmapClientError(RuntimeError):
    def __init__(self, message: str, *, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


class AmapClient:
    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._http_client = http_client

    def _request(self, endpoint: str, *, keywords: str, city: str) -> dict[str, object]:
        keywords = keywords.strip()
        city = city.strip()
        if not keywords:
            raise AmapClientError("查询关键词不能为空", kind="invalid_request")
        if not city:
            raise AmapClientError("高德公交查询必须提供 city", kind="invalid_request")

        try:
            api_key = self.settings.require_amap_api_key()
        except RuntimeError as exc:
            raise AmapClientError(str(exc), kind="configuration") from exc

        params = {
            "key": api_key,
            "keywords": keywords,
            "city": city,
            "output": "json",
        }
        if endpoint == "v3/bus/linename":
            params["extensions"] = "all"

        url = urljoin(str(self.settings.amap_api_url), endpoint)
        try:
            if self._http_client is None:
                response = httpx.get(
                    url,
                    params=params,
                    timeout=self.settings.upstream_timeout_seconds,
                )
            else:
                response = self._http_client.get(
                    url,
                    params=params,
                    timeout=self.settings.upstream_timeout_seconds,
                )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AmapClientError(f"高德 API 请求失败: {exc}", kind="unavailable") from exc

        if not isinstance(payload, dict):
            raise AmapClientError("高德 API JSON 根节点不是对象", kind="invalid_response")
        if str(payload.get("status")) != "1":
            info = payload.get("info") or "未知错误"
            infocode = payload.get("infocode") or "unknown"
            raise AmapClientError(
                f"高德业务错误 {infocode}: {info}", kind="business_error"
            )
        return payload

    def query_stop(self, *, keywords: str, city: str) -> AmapStopResponseDTO:
        return AmapStopResponseDTO.model_validate(
            self._request("v3/bus/stopname", keywords=keywords, city=city)
        )

    def query_line(self, *, keywords: str, city: str) -> AmapLineResponseDTO:
        return AmapLineResponseDTO.model_validate(
            self._request("v3/bus/linename", keywords=keywords, city=city)
        )
