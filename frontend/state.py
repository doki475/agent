from __future__ import annotations

from typing import Any

from nicegui import app, ui


def save_session(token: str, user: dict[str, Any]) -> None:
    app.storage.user.update({"token": token, "user": user})


def clear_session() -> None:
    app.storage.user.pop("token", None)
    app.storage.user.pop("user", None)


def current_user() -> dict[str, Any] | None:
    user = app.storage.user.get("user")
    return user if isinstance(user, dict) else None


def require_user() -> dict[str, Any] | None:
    user = current_user()
    if not user:
        ui.navigate.to("/login")
    return user


def require_root() -> dict[str, Any] | None:
    user = require_user()
    if user and user.get("role") != "root":
        ui.navigate.to("/chat")
        return None
    return user
