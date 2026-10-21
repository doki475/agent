from __future__ import annotations

from nicegui import ui

from frontend.config import FRONTEND_PORT, STORAGE_SECRET
from frontend.pages import chat, knowledge, login, users  # noqa: F401
from frontend.state import current_user


@ui.page("/")
def index_page() -> None:
    ui.navigate.to("/chat" if current_user() else "/login")


ui.run(
    host="0.0.0.0",
    port=FRONTEND_PORT,
    title="出行计划助手",
    storage_secret=STORAGE_SECRET,
    reload=False,
    show=False,
)
