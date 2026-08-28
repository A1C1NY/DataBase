"""Synchronous HTTPX client for Amap bus stop and line endpoints."""

from threading import Lock
from time import monotonic, sleep
from typing import ClassVar
from urllib.parse import urljoin

import httpx

from app.core.config import Settings, get_settings
from app.integrations.amap.schemas import AmapLineResponseDTO, AmapStopResponseDTO


class AmapClientError(RuntimeError):
    def __init__(self, message: str, *, kind: str, infocode: str | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.infocode = infocode


class AmapClient:
    _rate_limit_lock: ClassVar[Lock] = Lock()
    _last_request_at: ClassVar[dict[str, float]] = {}

    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._http_client = http_client

    @classmethod
    def _wait_for_request_slot(cls, group: str, min_interval: float) -> None:
        with cls._rate_limit_lock:
            last_request_at = cls._last_request_at.get(group)
            if last_request_at is not None:
                elapsed = monotonic() - last_request_at
                remaining = min_interval - elapsed
                if remaining > 0:
                    sleep(remaining)
            cls._last_request_at[group] = monotonic()

    def _send(
        self,
        url: str,
        params: dict[str, str],
        *,
        rate_limit_group: str,
        min_interval: float,
    ) -> dict[str, object]:
        self._wait_for_request_slot(rate_limit_group, min_interval)
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
        return payload

    def _request(
        self,
        endpoint: str,
        *,
        query_params: dict[str, str],
        rate_limit_group: str,
        min_interval: float,
    ) -> dict[str, object]:
        try:
            api_key = self.settings.require_amap_api_key()
        except RuntimeError as exc:
            raise AmapClientError(str(exc), kind="configuration") from exc

        params = {
            "key": api_key,
            "output": "json",
            **query_params,
        }
        if endpoint in {"v3/bus/linename", "v3/bus/lineid"}:
            params["extensions"] = "all"

        url = urljoin(str(self.settings.amap_api_url), endpoint)
        for attempt in range(self.settings.amap_rate_limit_retries + 1):
            payload = self._send(
                url,
                params,
                rate_limit_group=rate_limit_group,
                min_interval=min_interval,
            )
            if str(payload.get("status")) == "1":
                return payload
            info = payload.get("info") or "未知错误"
            infocode = str(payload.get("infocode") or "unknown")
            if infocode == "10021" and attempt < self.settings.amap_rate_limit_retries:
                sleep(self.settings.amap_rate_limit_backoff_seconds * (2**attempt))
                continue
            raise AmapClientError(
                f"高德业务错误 {infocode}: {info}",
                kind="business_error",
                infocode=infocode,
            )
        raise AssertionError("unreachable")

    def query_stop(self, *, keywords: str, city: str) -> AmapStopResponseDTO:
        keywords = keywords.strip()
        city = city.strip()
        if not keywords:
            raise AmapClientError("查询关键词不能为空", kind="invalid_request")
        if not city:
            raise AmapClientError("高德公交查询必须提供 city", kind="invalid_request")
        return AmapStopResponseDTO.model_validate(
            self._request(
                "v3/bus/stopname",
                query_params={"keywords": keywords, "city": city},
                rate_limit_group="keyword",
                min_interval=self.settings.amap_min_request_interval_seconds,
            )
        )

    def query_line(self, *, keywords: str, city: str) -> AmapLineResponseDTO:
        keywords = keywords.strip()
        city = city.strip()
        if not keywords:
            raise AmapClientError("查询关键词不能为空", kind="invalid_request")
        if not city:
            raise AmapClientError("高德公交查询必须提供 city", kind="invalid_request")
        return AmapLineResponseDTO.model_validate(
            self._request(
                "v3/bus/linename",
                query_params={"keywords": keywords, "city": city},
                rate_limit_group="keyword",
                min_interval=self.settings.amap_min_request_interval_seconds,
            )
        )

    def query_line_by_id(self, *, amap_line_id: str) -> AmapLineResponseDTO:
        amap_line_id = amap_line_id.strip()
        if not amap_line_id:
            raise AmapClientError("高德公交线路 ID 不能为空", kind="invalid_request")
        return AmapLineResponseDTO.model_validate(
            self._request(
                "v3/bus/lineid",
                query_params={"id": amap_line_id},
                rate_limit_group="lineid",
                min_interval=self.settings.amap_line_id_min_request_interval_seconds,
            )
        )
