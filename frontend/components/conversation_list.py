from __future__ import annotations

from typing import Any

from nicegui import ui

from frontend.api_client import ApiError, api


async def render_conversation_list(current_id: str | None) -> None:
    with ui.column().classes("w-full gap-2"):
        async def new_conversation() -> None:
            try:
                data = await api.post("/conversations")
                conversation = data.get("conversation", data) if isinstance(data, dict) else {}
                conversation_id = conversation.get("id")
                if not conversation_id:
                    raise ApiError("INVALID_RESPONSE", "新建会话响应缺少会话编号", 500)
                ui.navigate.to(f"/chat/{conversation_id}")
            except ApiError as exc:
                ui.notify(exc.message, type="negative")

        ui.button("新建对话", icon="add", on_click=new_conversation).classes("w-full").props("unelevated")
        try:
            data = await api.get("/conversations")
        except ApiError as exc:
            ui.label(exc.message).classes("text-sm text-red-600")
            return

        conversations = data.get("items", []) if isinstance(data, dict) else []
        if not conversations:
            ui.label("开始第一次出行规划").classes("py-4 text-center text-sm text-slate-500")
            return
        for conversation in conversations:
            if not isinstance(conversation, dict):
                continue
            conversation_id = str(conversation.get("id", ""))
            with ui.card().classes(
                "w-full cursor-pointer p-3 "
                + ("border-blue-400 bg-blue-50" if conversation_id == current_id else "hover:bg-slate-50")
            ).on("click", lambda _, cid=conversation_id: ui.navigate.to(f"/chat/{cid}")):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label(conversation.get("title") or "新对话").classes("font-medium")
                    with ui.button(icon="more_vert").props("flat dense").on("click.stop"):
                        with ui.menu():
                            async def rename(cid=conversation_id, old=conversation.get("title") or "") -> None:
                                with ui.dialog() as dialog, ui.card():
                                    title = ui.input("新标题", value=old).classes("w-72")
                                    async def save() -> None:
                                        try:
                                            await api.patch(f"/conversations/{cid}", json={"title": title.value})
                                            ui.notify("标题已更新", type="positive")
                                            ui.navigate.to(f"/chat/{current_id or ''}")
                                        except ApiError as exc:
                                            ui.notify(exc.message, type="negative")
                                        dialog.close()
                                    ui.button("保存", on_click=save)
                                dialog.open()

                            async def delete(cid=conversation_id) -> None:
                                with ui.dialog() as dialog, ui.card():
                                    ui.label("删除后无法恢复，确定删除此会话吗？")
                                    async def confirm() -> None:
                                        try:
                                            await api.delete(f"/conversations/{cid}")
                                            ui.notify("会话已删除", type="positive")
                                            ui.navigate.to("/chat" if cid == current_id else f"/chat/{current_id}")
                                        except ApiError as exc:
                                            ui.notify(exc.message, type="negative")
                                        dialog.close()
                                    with ui.row():
                                        ui.button("取消", on_click=dialog.close).props("flat")
                                        ui.button("删除", on_click=confirm).props("color=negative")
                                dialog.open()

                            ui.menu_item("重命名", on_click=rename)
                            ui.menu_item("删除", on_click=delete)
                details = []
                if conversation.get("message_count") is not None:
                    details.append(f"{conversation['message_count']} 条")
                if conversation.get("has_itinerary"):
                    details.append("已生成行程")
                if details:
                    ui.label(" · ".join(details)).classes("text-xs text-slate-500")
