from __future__ import annotations

import re
from typing import Any

from nicegui import ui


BREAKDOWN_COLORS = ["#4f46e5", "#0891b2", "#16a34a", "#f59e0b", "#e11d48", "#64748b"]


def _money(cents: Any) -> str:
    try:
        return f"¥{int(cents) // 100}"
    except (TypeError, ValueError):
        return "—"


def _duration(minutes: Any) -> str:
    try:
        total = int(minutes)
    except (TypeError, ValueError):
        return ""
    if total >= 60:
        hours, remainder = divmod(total, 60)
        return f"{hours} 小时" + (f" {remainder} 分" if remainder else "")
    return f"{total} 分钟"


def safe_name(name: Any) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "-", str(name or "行程")).strip(" .-")
    return (cleaned or "行程")[:64]


def build_markdown(itinerary: dict[str, Any]) -> str:
    title = str(itinerary.get("title") or "出行计划")
    lines = [f"# {title}", ""]
    destination = itinerary.get("destination") or {}
    if isinstance(destination, dict) and destination.get("name"):
        adcode = destination.get("adcode")
        suffix = f"（adcode {adcode}）" if adcode else ""
        lines.append(f"- 目的地：{destination['name']}{suffix}")
    start, end = itinerary.get("start_date"), itinerary.get("end_date")
    if start or end:
        lines.append(f"- 日期：{start or '—'} ~ {end or '—'}（{itinerary.get('day_count', '—')} 天）")
    travelers = itinerary.get("travelers") or {}
    if isinstance(travelers, dict):
        lines.append(f"- 出行人数：{travelers.get('adults', 0)} 成人，{travelers.get('children', 0)} 儿童")
    budget = itinerary.get("budget") or {}
    if isinstance(budget, dict) and budget.get("total_cent") is not None:
        lines.append(f"- 预算：{_money(budget['total_cent'])}")
    lines.extend(["", "## 行程"])

    days = itinerary.get("days")
    for index, day in enumerate(days if isinstance(days, list) else [], 1):
        if not isinstance(day, dict):
            continue
        date = str(day.get("date") or "")
        lines.extend(["", f"### 第 {index} 天 · {date} · {day.get('weekday', '')} · {day.get('theme', '')}"])
        weather = day.get("weather")
        if isinstance(weather, dict):
            lines.append(f"> 天气：{weather.get('condition', '')} {weather.get('temp_low_c', '')}–{weather.get('temp_high_c', '')}℃")
        items = day.get("items")
        if not isinstance(items, list) or not items:
            lines.append("- 自由活动")
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            time = f"{item.get('start_time') or '—'}–{item.get('end_time') or '—'}"
            lines.append(f"- {time} **{item.get('title', '行程安排')}**")
            location = item.get("location") or {}
            if isinstance(location, dict) and (location.get("address") or location.get("name")):
                lines.append(f"  - 位置：{location.get('address') or location.get('name')}")
            if item.get("cost_cent") is not None:
                cost = "免费" if item["cost_cent"] == 0 else _money(item["cost_cent"])
                lines.append(f"  - 费用：{cost}｜时长：{_duration(item.get('duration_min'))}")
            if item.get("notes"):
                lines.append(f"  - 备注：{item['notes']}")
    risks = itinerary.get("risks")
    if isinstance(risks, list) and risks:
        lines.extend(["", "## 风险提示"])
        for risk in risks:
            if isinstance(risk, dict):
                lines.append(f"- {risk.get('description', '')} → {risk.get('mitigation', '')}")
    packing = itinerary.get("packing_list")
    if isinstance(packing, list) and packing:
        lines.extend(["", f"**建议携带**：{'、'.join(map(str, packing))}"])
    return "\n".join(lines)


def render_itinerary_card(itinerary: Any) -> None:
    if not isinstance(itinerary, dict) or not isinstance(itinerary.get("days"), list) or not itinerary["days"]:
        return
    try:
        with ui.card().classes("w-full border border-slate-200 shadow-sm"):
            with ui.row().classes("w-full items-start justify-between"):
                with ui.column().classes("gap-1"):
                    ui.label(itinerary.get("title") or "出行计划").classes("text-xl font-bold")
                    travelers = itinerary.get("travelers") or {}
                    people = f"{travelers.get('adults', 0)} 人" if isinstance(travelers, dict) else ""
                    children = travelers.get("children", 0) if isinstance(travelers, dict) else 0
                    if children:
                        people += f" +{children} 儿童"
                    ui.label(
                        f"{itinerary.get('start_date', '日期待定')} ~ {itinerary.get('end_date', '日期待定')}"
                        f" · {itinerary.get('day_count', len(itinerary['days']))} 天 · {people}"
                    ).classes("text-sm text-slate-500")
                ui.button(
                    "导出行程",
                    icon="download",
                    on_click=lambda: ui.download.content(
                        build_markdown(itinerary).encode("utf-8"),
                        filename=f"{safe_name(itinerary.get('title'))}.md",
                    ),
                ).props("outline")

            budget = itinerary.get("budget")
            if isinstance(budget, dict):
                breakdown = budget.get("breakdown")
                if isinstance(breakdown, list) and breakdown:
                    total = max(sum(int(entry.get("amount_cent", entry.get("cost_cent", 0)) or 0)
                                    for entry in breakdown if isinstance(entry, dict)), 1)
                    with ui.row().classes("w-full items-center gap-3"):
                        ui.label(f"预算 {_money(budget.get('total_cent'))}").classes("font-medium")
                        with ui.row().classes("h-3 flex-1 overflow-hidden rounded-full gap-0"):
                            for index, entry in enumerate(breakdown):
                                if not isinstance(entry, dict):
                                    continue
                                cents = int(entry.get("amount_cent", entry.get("cost_cent", 0)) or 0)
                                label = str(entry.get("name") or entry.get("category") or "其他")
                                ui.element("div").style(
                                    f"width:{max(cents / total * 100, 1)}%;background:{BREAKDOWN_COLORS[index % len(BREAKDOWN_COLORS)]}"
                                ).tooltip(f"{label} {_money(cents)}")

            for index, day in enumerate(itinerary["days"], 1):
                if not isinstance(day, dict):
                    continue
                date = str(day.get("date") or "")
                weather = day.get("weather")
                weather_text = ""
                if isinstance(weather, dict):
                    weather_text = (
                        f"{weather.get('condition', '')} "
                        f"{weather.get('temp_low_c', '')}–{weather.get('temp_high_c', '')}℃"
                    )
                with ui.expansion(
                    f"第 {index} 天 · {date} · {day.get('weekday', '')} · {day.get('theme', '')}",
                    icon="today",
                ).classes("w-full").props("default-opened"):
                    if weather_text:
                        ui.badge(weather_text, color="blue-1").classes("text-blue-900")
                    items = day.get("items")
                    if not isinstance(items, list) or not items:
                        ui.label("自由活动").classes("py-3 text-slate-500")
                    for item in items if isinstance(items, list) else []:
                        if not isinstance(item, dict):
                            continue
                        inferred = item.get("source") == "model"
                        with ui.card().classes("w-full").style(
                            "background:rgba(100,116,139,.04);border-left:3px solid #94a3b8"
                            if inferred else "box-shadow:none;border:0;border-bottom:1px solid #e2e8f0"
                        ):
                            if inferred:
                                ui.badge("模型推断", color="grey-3").classes("self-end text-slate-600")
                            start, end = item.get("start_time"), item.get("end_time")
                            time_text = f"{start}–{end}" if start and end else "时间待定"
                            ui.label(f"{time_text}  {item.get('title', '行程安排')}").classes("font-semibold")
                            location = item.get("location") or {}
                            if isinstance(location, dict):
                                address = location.get("address") or location.get("name")
                                if address:
                                    ui.label(f"📍 {address}").classes("text-sm text-slate-600")
                            details = []
                            if item.get("cost_cent") is not None:
                                details.append("免费" if item["cost_cent"] == 0 else _money(item["cost_cent"]))
                            duration = _duration(item.get("duration_min"))
                            if duration:
                                details.append(duration)
                            if details:
                                ui.label(" · ".join(details)).classes("text-sm text-slate-500")
                            transport = item.get("transport")
                            if isinstance(transport, dict):
                                transport = " ".join(str(transport.get(k)) for k in ("mode", "duration_min", "distance_m") if transport.get(k) is not None)
                            if transport:
                                ui.label(f"↳ {transport}").classes("text-sm text-slate-500")
                            if item.get("notes"):
                                ui.label(f"💡 {item['notes']}").classes("text-sm text-amber-800")
            risks = itinerary.get("risks")
            if isinstance(risks, list) and risks:
                with ui.expansion("⚠ 风险提示", icon="warning").classes("w-full"):
                    for risk in risks:
                        if isinstance(risk, dict):
                            ui.label(f"· {risk.get('description', '')} → {risk.get('mitigation', '')}")
            packing = itinerary.get("packing_list")
            if isinstance(packing, list) and packing:
                ui.label(f"🧳 建议携带：{'、'.join(map(str, packing))}").classes("text-sm text-slate-600")
    except (TypeError, ValueError, KeyError, AttributeError):
        # A malformed enhancement should never hide the assistant's text response.
        return
