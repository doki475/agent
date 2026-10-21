from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from frontend.config import WS_URL


class ChatSocket:
    """WebSocket transport; frame consumers should enqueue data for UI polling."""

    def __init__(self, on_frame: Callable[[dict[str, Any]], None], url: str = WS_URL) -> None:
        self._url = url
        self._on_frame = on_frame
        self._ws: Any = None
        self._reader: asyncio.Task[None] | None = None
        self._closed = False
        self._send_lock = asyncio.Lock()
        self._token = ""

    async def connect(self, token: str) -> None:
        self._closed = False
        self._ws = await websockets.connect(self._url, max_size=1 << 20)
        await self._ws.send(json.dumps({"type": "auth", "data": {"token": token}}))
        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=10)
            frame = json.loads(raw)
        except (asyncio.TimeoutError, ConnectionClosed, json.JSONDecodeError) as exc:
            await self._ws.close()
            raise ConnectionError("WebSocket authentication did not complete") from exc
        if frame.get("type") != "auth_ok":
            await self._ws.close()
            raise PermissionError("WebSocket authentication failed")
        self._on_frame(frame)
        self._reader = asyncio.create_task(self._reader_loop())

    async def send_message(self, conversation_id: str, content: str) -> None:
        await self._send({"type": "message", "data": {"conversation_id": conversation_id, "content": content}})

    async def send_cancel(self, conversation_id: str) -> None:
        await self._send({"type": "cancel", "data": {"conversation_id": conversation_id}})

    async def _send(self, frame: dict[str, Any]) -> None:
        if self._ws is None:
            raise ConnectionError("WebSocket is not connected")
        async with self._send_lock:
            await self._ws.send(json.dumps(frame, ensure_ascii=False))

    async def _reader_loop(self) -> None:
        while not self._closed:
            try:
                async for raw in self._ws:
                    try:
                        frame = json.loads(raw)
                    except json.JSONDecodeError:
                        self._on_frame({"type": "_protocol_error", "data": None})
                        continue
                    if isinstance(frame, dict):
                        self._on_frame(frame)
            except ConnectionClosed:
                pass
            if self._closed:
                return
            self._on_frame({"type": "_disconnected", "data": None})
            if not await self._reconnect_loop():
                return

    async def _reconnect_loop(self) -> bool:
        for delay in (1, 2, 4, 8, 8):
            if self._closed:
                return False
            await asyncio.sleep(delay)
            if self._closed:
                return False
            try:
                self._ws = await websockets.connect(self._url, max_size=1 << 20)
                await self._ws.send(json.dumps({"type": "auth", "data": {"token": self._token}}))
                raw = await asyncio.wait_for(self._ws.recv(), timeout=10)
                frame = json.loads(raw)
                if frame.get("type") != "auth_ok":
                    self._on_frame({"type": "_auth_failed", "data": None})
                    await self.close()
                    return False
                self._on_frame({"type": "_reconnected", "data": None})
                return True
            except Exception:
                continue
        self._on_frame({"type": "_gaveup", "data": None})
        return False

    async def close(self) -> None:
        self._closed = True
        if self._ws is not None:
            await self._ws.close()
        if self._reader and self._reader is not asyncio.current_task():
            self._reader.cancel()

    async def authenticate(self, token: str) -> None:
        self._token = token
        await self.connect(token)
