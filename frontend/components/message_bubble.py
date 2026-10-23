from __future__ import annotations

import re
from typing import Any

from nicegui import ui

from frontend.components.itinerary_card import render_itinerary_card

# 助手回复里附带的 ```json 是内部行程数据，页面上不直接展示。
# 只匹配语言为 json 的围栏代码块；未闭合的（流式输出中）也一并隐藏。
_JSON_FENCE_RE = re.compile(r"```[ \t]*json\b.*?(?:```|\Z)", re.IGNORECASE | re.DOTALL)


def _strip_json_blocks(text: str) -> str:
    """移除 Markdown 中的 ```json 代码块，其余内容不变。"""
    return _JSON_FENCE_RE.sub("", text).strip()


# 行内短语标签：蓝=交通，绿=室内/舒适
_TAG_PHRASES = (
    ("建议打车", "blue"),
    ("打车直达", "blue"),
    ("打车前往", "blue"),
    ("室内参观", "green"),
    ("避雨首选", "green"),
    ("长辈体力友好", "green"),
    ("减少步行", "green"),
    ("坐着休息", "green"),
)
_TAG_CLASS = {"blue": "tpa-tag tpa-tag-blue", "green": "tpa-tag tpa-tag-green"}
_HIGHLIGHT_PATTERNS = (
    re.compile(r"评分\s*\d+(?:\.\d+)?"),
    re.compile(r"\d+(?:\.\d+)?\s*元"),
)
# 代码块/行内代码不参与标签和高亮处理
_CODE_SPAN_RE = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)


def _decorate_markdown(text: str) -> str:
    """把交通/舒适短语变成标签，评分和价格用主题色强调。"""
    parts = _CODE_SPAN_RE.split(text)
    for i in range(0, len(parts), 2):
        segment = parts[i]
        for phrase, color in _TAG_PHRASES:
            segment = segment.replace(phrase, f'<span class="{_TAG_CLASS[color]}">{phrase}</span>')
        for pattern in _HIGHLIGHT_PATTERNS:
            segment = pattern.sub(
                lambda match: f'<strong class="tpa-highlight">{match.group(0)}</strong>',
                segment,
            )
        parts[i] = segment
    return "".join(parts)


def render_message(message: dict[str, Any], on_retry=None) -> None:
    role = message.get("role")
    content = str(message.get("content") or "")
    is_user = role == "user"
    with ui.row().classes(f"w-full {'justify-end' if is_user else 'justify-start'}"):
        with ui.card().classes(
            "max-w-[85%] min-w-0 rounded-2xl "
            + ("message-card-user" if is_user else "message-card-ai")
        ):
            if is_user:
                ui.label(content).classes("whitespace-pre-wrap")
            elif content:
                visible_content = _decorate_markdown(_strip_json_blocks(content))
                if visible_content:
                    # w-full + min-w-0：允许 Markdown 收缩到卡片宽度，不被代码块撑开
                    ui.markdown(visible_content).classes("message-markdown prose w-full min-w-0 max-w-full")
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
