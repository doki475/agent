from __future__ import annotations

import asyncio
from collections import deque
from typing import Any, Optional

from nicegui import app, ui

from frontend.api_client import ApiError, api
from frontend.components.conversation_list import render_conversation_list
from frontend.components.message_bubble import render_message
from frontend.state import clear_session, current_user, save_session
from frontend.ws_client import ChatSocket

SUGGESTIONS = [
    "这周末去杭州玩两天，两个人，预算 1500",
    "下周去成都出差三天，有什么值得去的地方",
    "带爸妈去苏州一日游，不想走太多路",
]
TOOL_LABELS = {
    "weather_now": "正在查询实时天气…",
    "weather_forecast": "正在查询天气预报…",
    "place_search": "正在搜索地点…",
    "geo_geocode": "正在定位地址…",
    "route_plan": "正在计算路线…",
    "search_knowledge_base": "正在检索知识库…",
}


async def _verify_session() -> dict[str, Any] | None:
    if not current_user():
        ui.navigate.to("/login")
        return None
    try:
        result = await api.get("/auth/me")
        user = result.get("user", result) if isinstance(result, dict) else None
        if not isinstance(user, dict):
            ui.notify("登录信息无效，请重新登录", type="negative")
            clear_session()
            ui.navigate.to("/login")
            return None
        save_session(app.storage.user.get("token", ""), user)
        return user
    except ApiError:
        return None


@ui.page("/chat")
@ui.page("/chat/{conversation_id}")
async def chat_page(conversation_id: Optional[str] = None) -> None:
    user = await _verify_session()
    if not user:
        return

    ui.add_head_html("""
    <style>
      body { background:#f8fafc; }
      .chat-scroll { scrollbar-width:thin; }
      .message-input textarea { min-height:64px; }
    </style>
    """)
    with ui.header().classes("items-center justify-between bg-white text-slate-800 shadow-sm"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("travel_explore", size="sm").classes("text-indigo-600")
            ui.label("出行计划助手").classes("text-lg font-bold")
        with ui.row().classes("items-center gap-3"):
            ui.label(user.get("username", "用户")).classes("text-sm text-slate-500")
            if user.get("role") == "root":
                ui.link("知识库", "/knowledge").classes("text-sm")
                ui.link("用户管理", "/users").classes("text-sm")
            async def logout() -> None:
                clear_session()
                ui.navigate.to("/login")
            ui.button("退出", icon="logout", on_click=logout).props("flat dense")

    with ui.row().classes("w-full items-stretch gap-0"):
        with ui.column().classes("hidden h-[calc(100vh-64px)] w-72 shrink-0 overflow-y-auto border-r border-slate-200 bg-white p-4 md:flex"):
            await render_conversation_list(conversation_id)

        with ui.column().classes("relative h-[calc(100vh-64px)] min-w-0 flex-1"):
            connection_banner = ui.label("").classes("hidden w-full bg-amber-100 px-4 py-2 text-sm text-amber-900")
            thinking_bar = ui.label("").classes("hidden w-full px-6 py-2 text-sm text-indigo-700")
            with ui.scroll_area().classes("chat-scroll w-full flex-1"):
                message_area = ui.column().classes("mx-auto w-full max-w-4xl gap-4 px-4 py-6")
            with ui.column().classes("w-full border-t border-slate-200 bg-white px-4 py-4"):
                if not conversation_id:
                    with ui.column().classes("mx-auto w-full max-w-3xl items-center py-8 text-center"):
                        ui.label("把目的地、日期、人数和预算告诉我").classes("text-2xl font-bold")
                        ui.label("我会结合天气、地点和路线，帮你整理一份可执行的计划。").classes("text-slate-500")
                        with ui.row().classes("mt-3 flex-wrap justify-center"):
                            for suggestion in SUGGESTIONS:
                                ui.button(suggestion, on_click=lambda s=suggestion: text_input.set_value(s)).props("outline no-caps").classes("text-xs")
                with ui.row().classes("mx-auto w-full max-w-4xl items-end gap-2"):
                    text_input = ui.textarea(placeholder="说说你想去哪里、什么时候出发…").classes("message-input flex-1").props("autogrow outlined")
                    send_button = ui.button("发送", icon="send").props("unelevated")

    messages: list[dict[str, Any]] = []
    if conversation_id:
        try:
            data = await api.get(f"/conversations/{conversation_id}/messages")
            messages = data.get("items", []) if isinstance(data, dict) else []
        except ApiError as exc:
            ui.notify(exc.message, type="negative")
            ui.navigate.to("/chat")
            return

    def draw_messages() -> None:
        message_area.clear()
        with message_area:
            if not messages and conversation_id:
                ui.label("告诉我你要去哪、什么时候、几个人、预算多少").classes("my-20 self-center text-center text-slate-500")
            for index, message in enumerate(messages):
                async def retry(message=message, index=index) -> None:
                    await retry_message(message, index)
                render_message(message, on_retry=retry)

    draw_messages()

    frames: deque[dict[str, Any]] = deque()
    socket: ChatSocket | None = None
    streaming = False
    cancelling = False
    buffer = ""
    round_user_message = ""
    latest_tool: str | None = None

    def on_frame(frame: dict[str, Any]) -> None:
        frames.append(frame)

    async def open_socket() -> None:
        nonlocal socket
        token = app.storage.user.get("token")
        if not token:
            return
        socket = ChatSocket(on_frame)
        try:
            await socket.authenticate(token)
        except PermissionError:
            clear_session()
            ui.navigate.to("/login")
        except Exception:
            frames.append({"type": "_connect_failed", "data": None})

    asyncio.create_task(open_socket())

    def update_ui_state() -> None:
        busy = streaming or cancelling
        text_input.set_enabled(not busy)
        send_button.set_text("停止" if streaming and not cancelling else "发送")
        send_button.props("icon=stop" if streaming and not cancelling else "icon=send")
        send_button.set_enabled(not cancelling)

    async def backfill() -> None:
        if not conversation_id:
            return
        try:
            data = await api.get(f"/conversations/{conversation_id}/messages")
            messages[:] = data.get("items", []) if isinstance(data, dict) else []
            draw_messages()
        except ApiError as exc:
            ui.notify(exc.message, type="negative")

    async def poll_frames() -> None:
        nonlocal streaming, cancelling, buffer, latest_tool
        changed = False
        while frames:
            frame = frames.popleft()
            kind, data = frame.get("type"), frame.get("data") or {}
            if kind == "_disconnected":
                connection_banner.set_text("连接已断开，正在重连…")
                connection_banner.classes(remove="hidden")
            elif kind == "_reconnected":
                connection_banner.classes(add="hidden")
                streaming = False
                cancelling = False
                update_ui_state()
                await backfill()
            elif kind == "_gaveup":
                connection_banner.set_text("连接已断开，请刷新页面")
                connection_banner.classes(remove="hidden")
            elif kind == "_auth_failed":
                clear_session()
                ui.navigate.to("/login")
            elif kind == "_connect_failed":
                connection_banner.set_text("实时连接不可用，将尝试普通消息接口")
                connection_banner.classes(remove="hidden")
            elif kind == "_protocol_error":
                ui.notify("收到无法识别的实时消息", type="warning")
            elif kind == "tool":
                tool_name = str(data.get("name") or "")
                phase = data.get("phase")
                if phase == "start":
                    latest_tool = tool_name
                    thinking_bar.set_text(TOOL_LABELS.get(tool_name, f"正在调用 {tool_name}…"))
                    thinking_bar.classes(remove="hidden")
                elif phase == "end":
                    thinking_bar.set_text("正在组织答案…")
                changed = True
            elif kind == "token":
                buffer += str(data.get("delta") or "")
                thinking_bar.classes(add="hidden")
                changed = True
            elif kind == "itinerary":
                changed = True
            elif kind == "error":
                message = str(data.get("message") or "生成失败")
                ui.notify(message, type="negative")
                if messages and messages[-1].get("role") == "assistant":
                    messages[-1]["status"] = "failed"
                    messages[-1]["error_message"] = message
                streaming = False
                cancelling = False
                thinking_bar.classes(add="hidden")
                update_ui_state()
                changed = True
            elif kind == "done":
                streaming = False
                cancelling = False
                thinking_bar.classes(add="hidden")
                update_ui_state()
                await backfill()
                buffer = ""
                changed = False
        if changed and streaming and messages and messages[-1].get("role") == "assistant":
            messages[-1]["content"] = buffer
            draw_messages()
        update_ui_state()

    ui.timer(0.06, poll_frames)

    async def send_content(content: str) -> None:
        nonlocal conversation_id, streaming, cancelling, buffer, round_user_message, socket
        if streaming or cancelling:
            if streaming and not cancelling and conversation_id and socket:
                try:
                    await socket.send_cancel(conversation_id)
                    cancelling = True
                    thinking_bar.set_text("正在停止…")
                    thinking_bar.classes(remove="hidden")
                    update_ui_state()
                    ui.timer(
                        3,
                        lambda: ui.notify("停止请求已发出，正在收尾", type="info") if cancelling else None,
                        once=True,
                    )
                except Exception as exc:
                    ui.notify(f"无法发送停止请求：{exc}", type="negative")
            return
        content = content.strip()
        if not content:
            return
        if len(content) > 8000:
            ui.notify("消息不能超过 8000 字", type="warning")
            return
        if socket is None:
            await open_socket()
        if not conversation_id:
            try:
                result = await api.post("/conversations")
                conversation = result.get("conversation", result) if isinstance(result, dict) else {}
                conversation_id = str(conversation["id"])
            except (ApiError, KeyError, TypeError) as exc:
                ui.notify(exc.message if isinstance(exc, ApiError) else "创建会话失败", type="negative")
                return
        round_user_message = content
        messages.append({"role": "user", "content": content})
        messages.append({"role": "assistant", "content": "", "status": "streaming"})
        buffer = ""
        streaming = True
        text_input.set_value("")
        draw_messages()
        update_ui_state()
        thinking_bar.set_text("正在思考…")
        thinking_bar.classes(remove="hidden")
        try:
            if socket:
                await socket.send_message(conversation_id, content)
            else:
                raise ConnectionError("实时连接不可用")
        except Exception:
            # The documented REST endpoint is retained as a compatibility fallback.
            try:
                result = await api.post(f"/conversations/{conversation_id}/messages", json={"content": content})
                if messages:
                    messages[-1]["content"] = result.get("message", {}).get("content", "") if isinstance(result, dict) else ""
                    messages[-1]["status"] = "completed"
                streaming = False
                thinking_bar.classes(add="hidden")
                draw_messages()
                update_ui_state()
            except ApiError as exc:
                messages[-1]["status"] = "failed"
                messages[-1]["error_message"] = exc.message
                streaming = False
                thinking_bar.classes(add="hidden")
                draw_messages()
                update_ui_state()

    async def retry_message(message: dict[str, Any], index: int | None = None) -> None:
        content = ""
        if index is not None:
            for previous in reversed(messages[:index]):
                if previous.get("role") == "user":
                    content = str(previous.get("content") or "")
                    break
        content = content or round_user_message or str(message.get("content") or "")
        await send_content(content)

    async def submit() -> None:
        await send_content(str(text_input.value or ""))

    send_button.on_click(submit)
    text_input.on("keydown.enter.prevent", lambda: submit())
