from __future__ import annotations

from typing import Any

from nicegui import ui

from frontend.components.itinerary_card import render_itinerary_card


def render_message(message: dict[str, Any], on_retry=None) -> None:
    role = message.get("role")
    content = str(message.get("content") or "")
    is_user = role == "user"
    with ui.row().classes(f"w-full {'justify-end' if is_user else 'justify-start'}"):
        with ui.card().classes(
            "max-w-[85%] rounded-2xl "
            + ("bg-indigo-600 text-white" if is_user else "bg-white border border-slate-200")
        ):
            if is_user:
                ui.label(content).classes("whitespace-pre-wrap")
            elif content:
                ui.markdown(content).classes("prose max-w-none")
            if message.get("status") == "failed":
                with ui.row().classes("items-center text-red-700"):
                    ui.icon("error_outline")
                    ui.label(message.get("error_message") or "生成失败，请重试")
                    if on_retry:
                        ui.button("重试", icon="refresh", on_click=lambda: on_retry(message)).props("flat dense")
            if message.get("status") == "cancelled":
                ui.label("已停止生成").classes("text-xs text-slate-500")
            itinerary = message.get("itinerary")
            if not is_user and itinerary is not None:
                render_itinerary_card(itinerary)
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list) and tool_calls:
                with ui.expansion(f"🔧 已调用 {len(tool_calls)} 个工具", icon="build").classes("w-full"):
                    for tool in tool_calls:
                        if not isinstance(tool, dict):
                            continue
                        ok = tool.get("ok", True)
                        label = "✔" if ok else "✖"
                        name = tool.get("name", "tool")
                        elapsed = tool.get("duration_ms")
                        detail = tool.get("summary") or tool.get("output_summary") or ""
                        ui.label(f"{label} {name}  {str(elapsed) + 'ms' if elapsed is not None else ''}  {detail}")
