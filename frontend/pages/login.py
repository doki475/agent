from __future__ import annotations

from nicegui import ui

from frontend.api_client import ApiError, api
from frontend.state import current_user, save_session


@ui.page("/login")
def login_page() -> None:
    if current_user():
        ui.navigate.to("/chat")
        return

    ui.add_head_html("""
    <style>
      body { background: radial-gradient(circle at 20% 10%, #e0e7ff, transparent 35%), #f8fafc; }
    </style>
    """)
    with ui.column().classes("absolute-center w-full max-w-md px-5"):
        with ui.card().classes("w-full rounded-3xl p-8 shadow-xl"):
            ui.label("出行计划助手").classes("text-3xl font-bold text-slate-900")
            ui.label("规划一次更从容的旅程").classes("mb-5 text-slate-500")
            tabs = ui.tabs().classes("w-full")
            login_tab = ui.tab("登录")
            register_tab = ui.tab("注册")
            panels = ui.tab_panels(tabs, value=login_tab).classes("w-full")
            with panels:
                with ui.tab_panel(login_tab):
                    username = ui.input("用户名").classes("w-full").props("autocomplete=username")
                    password = ui.input("密码", password=True, password_toggle_button=True).classes("w-full").props("autocomplete=current-password")
                    error_label = ui.label("").classes("text-sm text-red-600")

                    async def submit_login() -> None:
                        error_label.set_text("")
                        try:
                            result = await api.post("/auth/login", json={"username": username.value, "password": password.value})
                            save_session(result["token"], result["user"])
                            ui.navigate.to("/chat")
                        except (ApiError, KeyError, TypeError) as exc:
                            message = exc.message if isinstance(exc, ApiError) else "登录响应格式不正确"
                            error_label.set_text("用户名或密码错误" if isinstance(exc, ApiError) and exc.code == "AUTH_BAD_CREDENTIALS" else message)

                    ui.button("进入", on_click=submit_login).classes("mt-3 w-full").props("unelevated")
                    username.on("keydown.enter", submit_login)
                    password.on("keydown.enter", submit_login)
                with ui.tab_panel(register_tab):
                    new_username = ui.input("用户名").classes("w-full").props("autocomplete=username")
                    new_password = ui.input("密码（至少 8 位）", password=True, password_toggle_button=True).classes("w-full").props("autocomplete=new-password")
                    register_error = ui.label("").classes("text-sm text-red-600")
                    ui.label("注册后将自动登录。").classes("text-sm text-slate-500")

                    async def submit_register() -> None:
                        register_error.set_text("")
                        try:
                            result = await api.post("/auth/register", json={"username": new_username.value, "password": new_password.value})
                            save_session(result["token"], result["user"])
                            ui.navigate.to("/chat")
                        except (ApiError, KeyError, TypeError) as exc:
                            if isinstance(exc, ApiError):
                                messages = {
                                    "AUTH_WEAK_PASSWORD": "密码至少 8 位",
                                    "AUTH_USERNAME_TAKEN": "用户名已被占用",
                                    "AUTH_REGISTER_CLOSED": "请联系管理员开号",
                                }
                                register_error.set_text(messages.get(exc.code, exc.message))
                                if exc.code == "AUTH_REGISTER_CLOSED":
                                    register_tab.delete()
                            else:
                                register_error.set_text("注册响应格式不正确")

                    ui.button("创建账号", on_click=submit_register).classes("mt-3 w-full").props("unelevated")
                    new_password.on("keydown.enter", submit_register)
