from __future__ import annotations

from typing import Any

import httpx
from nicegui import app, ui

from frontend.config import API_PREFIX, BACKEND_BASE_URL
from frontend.state import clear_session


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class ApiClient:
    def __init__(self, base_url: str = BACKEND_BASE_URL) -> None:
        # 只访问本机后端，忽略系统代理（Windows 代理开着但没启动时，
        # httpx 会把 127.0.0.1 也发给代理，导致“无法连接服务器”）。
        self._client = httpx.AsyncClient(base_url=base_url, timeout=90, trust_env=False)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = path if path.startswith("http") else f"{API_PREFIX}{path}"
        headers = dict(kwargs.pop("headers", {}))
        token = app.storage.user.get("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = await self._client.request(method, url, headers=headers, **kwargs)
        except httpx.RequestError as exc:
            raise ApiError("NETWORK_ERROR", "无法连接服务器，请检查后端是否已启动", 0) from exc

        if response.status_code == 401:
            clear_session()
            ui.navigate.to("/login")
            raise ApiError("AUTH_TOKEN_INVALID", "登录已过期", 401)

        try:
            body = response.json()
        except ValueError as exc:
            raise ApiError("INVALID_RESPONSE", "服务器返回了无法识别的数据", response.status_code) from exc

        if not isinstance(body, dict) or not body.get("ok"):
            error = body.get("error", {}) if isinstance(body, dict) else {}
            if not isinstance(error, dict):
                error = {}
            raise ApiError(
                str(error.get("code", "INTERNAL_ERROR")),
                str(error.get("message", "请求失败")),
                response.status_code,
            )
        return body.get("data")

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return await self._request("POST", path, json=json)

    async def put(self, path: str, json: dict[str, Any]) -> Any:
        return await self._request("PUT", path, json=json)

    async def patch(self, path: str, json: dict[str, Any]) -> Any:
        return await self._request("PATCH", path, json=json)

    async def delete(self, path: str) -> Any:
        return await self._request("DELETE", path)

    async def upload(self, path: str, files: dict[str, Any], data: dict[str, Any]) -> Any:
        return await self._request("POST", path, files=files, data=data)


api = ApiClient()
