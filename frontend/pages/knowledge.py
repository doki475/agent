from __future__ import annotations

import asyncio
from typing import Any

from nicegui import ui

from frontend.api_client import ApiError, api
from frontend.pages.chat import _verify_session


@ui.page("/knowledge")
async def knowledge_page() -> None:
    user = await _verify_session()
    if not user:
        return
    if user.get("role") != "root":
        ui.navigate.to("/chat")
        return

    ui.add_head_html("<style>body{background:#f8fafc}</style>")
    with ui.header().classes("items-center justify-between bg-white text-slate-800 shadow-sm"):
        ui.label("知识库管理").classes("text-xl font-bold")
        ui.link("返回对话", "/chat")
    with ui.column().classes("mx-auto w-full max-w-6xl gap-5 p-6"):
        with ui.card().classes("w-full"):
            ui.label("添加知识").classes("text-lg font-semibold")
            title_input = ui.input("文档标题（可选）").classes("w-full")
            with ui.row().classes("items-center"):
                upload_status = ui.label("")
                async def upload_file(event) -> None:
                    upload_status.set_text("正在上传并处理…")
                    try:
                        content = await event.file.read()
                        result = await api.upload(
                            "/rag/documents",
                            files={"file": (event.file.name, content)},
                            data={"title": title_input.value or ""},
                        )
                        if result.get("status") == "ready":
                            ui.notify(f"入库成功，共 {result.get('chunk_count', 0)} 块", type="positive")
                        else:
                            ui.notify(f"入库失败：{result.get('error', '未知错误')}", type="negative")
                        await refresh_documents()
                    except ApiError as exc:
                        ui.notify(exc.message, type="negative")
                    finally:
                        upload_status.set_text("")
                ui.upload(on_upload=upload_file, auto_upload=True, max_file_size=20_000_000).props("accept=.pdf,.docx,.md,.txt,.csv")

            with ui.row().classes("w-full items-end"):
                source_url = ui.input("从网址添加", placeholder="https://example.com/notice").classes("flex-1")
                async def add_url() -> None:
                    try:
                        result = await api.post("/rag/documents/from-url", json={"url": source_url.value, "title": title_input.value or ""})
                        ui.notify(f"网址已提交：{result.get('status', '完成')}", type="positive")
                        await refresh_documents()
                    except ApiError as exc:
                        ui.notify(exc.message, type="negative")
                ui.button("添加网址", icon="link", on_click=add_url)

        with ui.card().classes("w-full"):
            ui.label("文档列表").classes("text-lg font-semibold")
            document_area = ui.column().classes("w-full")

        with ui.card().classes("w-full"):
            ui.label("检索调试").classes("text-lg font-semibold")
            query_input = ui.input("输入检索关键词").classes("w-full")
            search_status = ui.label("").classes("text-sm text-slate-500")
            search_results = ui.column().classes("w-full")
            debounce_task: asyncio.Task | None = None

            async def search_now(query: str) -> None:
                search_results.clear()
                if not query.strip():
                    search_status.set_text("")
                    return
                try:
                    result = await api.get("/rag/search", params={"q": query})
                    items = result.get("items", []) if isinstance(result, dict) else []
                    search_status.set_text(f"q={query} · {result.get('elapsed_ms', '—')}ms · 命中 {len(items)} 条")
                    with search_results:
                        if not items:
                            ui.label("没有匹配的片段。试试换关键词，或确认文档已入库").classes("text-slate-500")
                        for item in items:
                            with ui.card().classes("w-full bg-slate-50"):
                                ui.label(f"{item.get('title', '文档')} · 块#{item.get('chunk_index', '—')} · {item.get('score', '—')}").classes("font-medium")
                                ui.label(item.get("text", item.get("content", ""))).classes("whitespace-pre-wrap text-sm")
                except ApiError as exc:
                    search_status.set_text(exc.message)

            def schedule_search(event) -> None:
                nonlocal debounce_task
                if debounce_task:
                    debounce_task.cancel()
                debounce_task = asyncio.create_task(asyncio.sleep(0.5))
                async def delayed() -> None:
                    try:
                        await debounce_task
                        await search_now(str(event.value or ""))
                    except asyncio.CancelledError:
                        return
                asyncio.create_task(delayed())
            query_input.on_value_change(schedule_search)

    async def refresh_documents() -> None:
        document_area.clear()
        try:
            result = await api.get("/rag/documents")
            documents = result.get("items", []) if isinstance(result, dict) else []
            with document_area:
                if not documents:
                    ui.label("还没有文档。上传景区公告、交通新规等资料，助手回答时会引用它们。").classes("py-5 text-slate-500")
                for document in documents:
                    with ui.row().classes(
                        "w-full items-center justify-between rounded-lg px-3 py-2 "
                        + ("bg-red-50" if document.get("status") == "failed" else "hover:bg-slate-50")
                    ):
                        source_type = "网址" if document.get("source_type") == "url" else "文件"
                        ui.label(f"{document.get('title', '未命名')} · {source_type} · {document.get('status', '未知')} · {document.get('chunk_count', 0)} 块").classes("flex-1")
                        async def remove(doc_id=document.get("id")) -> None:
                            with ui.dialog() as dialog, ui.card():
                                ui.label("确定删除该知识文档吗？")
                                async def confirm() -> None:
                                    try:
                                        await api.delete(f"/rag/documents/{doc_id}")
                                        ui.notify("文档已删除", type="positive")
                                        await refresh_documents()
                                    except ApiError as exc:
                                        ui.notify(exc.message, type="negative")
                                    dialog.close()
                                with ui.row():
                                    ui.button("取消", on_click=dialog.close).props("flat")
                                    ui.button("删除", on_click=confirm).props("color=negative")
                            dialog.open()
                        ui.button(icon="delete", on_click=remove).props("flat dense color=negative")
        except ApiError as exc:
            with document_area:
                ui.label(exc.message).classes("text-red-600")

    await refresh_documents()
