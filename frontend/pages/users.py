from __future__ import annotations

from typing import Any

from nicegui import ui

from frontend.api_client import ApiError, api
from frontend.pages.chat import _verify_session


@ui.page("/users")
async def users_page() -> None:
    user = await _verify_session()
    if not user:
        return
    if user.get("role") != "root":
        ui.navigate.to("/chat")
        return

    ui.add_head_html("<style>body{background:#f8fafc}</style>")
    with ui.header().classes("items-center justify-between bg-white text-slate-800 shadow-sm"):
        ui.label("用户管理").classes("text-xl font-bold")
        ui.link("返回对话", "/chat")
    table_area = ui.column().classes("mx-auto w-full max-w-6xl gap-3 p-6")

    async def refresh_users() -> None:
        table_area.clear()
        try:
            result = await api.get("/admin/users")
            users = result.get("items", []) if isinstance(result, dict) else []
            active_roots = sum(1 for item in users if item.get("role") == "root" and item.get("status") == "active")
            with table_area:
                if not users:
                    ui.label("暂无用户")
                    return
                with ui.row().classes("w-full rounded-lg bg-slate-100 px-4 py-3 font-semibold"):
                    ui.label("用户名").classes("flex-1")
                    ui.label("角色").classes("w-20")
                    ui.label("状态").classes("w-24")
                    ui.label("会话数").classes("w-24")
                    ui.label("操作").classes("w-56")
                for item in users:
                    if not isinstance(item, dict):
                        continue
                    own = str(item.get("id")) == str(user.get("id"))
                    last_root = item.get("role") == "root" and item.get("status") == "active" and active_roots <= 1
                    with ui.row().classes("w-full items-center rounded-lg bg-white px-4 py-3 shadow-sm"):
                        ui.label(item.get("username", "—")).classes("flex-1")
                        ui.label(item.get("role", "user")).classes("w-20")
                        ui.label(item.get("status", "active")).classes("w-24")
                        ui.label(str(item.get("conversation_count", 0))).classes("w-24")
                        with ui.row().classes("w-56 justify-end"):
                            disabled = own or last_root
                            if item.get("role") == "root":
                                async def set_role(target=item, role="user") -> None:
                                    await update_user(target, {"role": role}, "修改用户角色")
                                ui.button("设为 user", on_click=set_role).props(f"flat dense {'disable' if disabled else ''}").tooltip("不能修改自己的账号" if own else "系统必须保留一个可用的 root" if last_root else "")
                            else:
                                async def set_role(target=item, role="root") -> None:
                                    await update_user(target, {"role": role}, "修改用户角色")
                                ui.button("设为 root", on_click=set_role).props(f"flat dense {'disable' if own else ''}").tooltip("不能修改自己的账号" if own else "")
                            next_status = "disabled" if item.get("status") == "active" else "active"
                            async def set_status(target=item, value=next_status) -> None:
                                await update_user(target, {"status": value}, "修改账号状态")
                            ui.button("禁用" if next_status == "disabled" else "启用", on_click=set_status).props(
                                f"flat dense {'disable' if disabled else ''}"
                            ).tooltip("不能修改自己的账号" if own else "系统必须保留一个可用的 root" if last_root else "")
        except ApiError as exc:
            with table_area:
                ui.label(exc.message).classes("text-red-600")

    async def update_user(target: dict[str, Any], changes: dict[str, Any], action: str) -> None:
        with ui.dialog() as dialog, ui.card():
            ui.label(f"确定要{action}：{target.get('username')}？")
            async def confirm() -> None:
                try:
                    await api.patch(f"/admin/users/{target.get('id')}", json=changes)
                    ui.notify("操作成功", type="positive")
                    await refresh_users()
                except ApiError as exc:
                    ui.notify(exc.message, type="negative")
                dialog.close()
            with ui.row():
                ui.button("取消", on_click=dialog.close).props("flat")
                ui.button("确认", on_click=confirm).props("unelevated")
        dialog.open()

    await refresh_users()
