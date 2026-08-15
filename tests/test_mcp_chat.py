"""Tests for MCP chat tool wrappers."""

import asyncio
import inspect
import threading
import time

import pytest

from notebooklm_tools.mcp.tools import chat as chat_tools
from notebooklm_tools.services.errors import ServiceError


def test_notebook_query_is_async_for_cancellable_dispatch():
    assert inspect.iscoroutinefunction(chat_tools.notebook_query)


@pytest.mark.asyncio
async def test_notebook_query_cancellation_does_not_wait_for_worker(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def slow_query(*args, **kwargs):
        started.set()
        release.wait()
        finished.set()
        return {
            "answer": "done",
            "conversation_id": None,
            "sources_used": [],
            "citations": {},
            "references": [],
        }

    monkeypatch.setattr(chat_tools, "get_client", lambda: object())
    monkeypatch.setattr(chat_tools.chat_service, "query", slow_query)

    task = asyncio.create_task(chat_tools.notebook_query("nb-123", "question"))
    assert await asyncio.to_thread(started.wait, 1.0)

    started_at = time.monotonic()
    task.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await task
        assert time.monotonic() - started_at < 0.5
        assert not finished.is_set()
    finally:
        release.set()

    assert await asyncio.to_thread(finished.wait, 1.0)


@pytest.mark.asyncio
async def test_notebook_query_returns_structured_service_error(monkeypatch):
    monkeypatch.setattr(chat_tools, "get_client", lambda: object())

    def rejected_query(*args, **kwargs):
        raise ServiceError(
            "provider rejected query",
            user_message="The query request is invalid.",
            hint="Check the source IDs.",
            debug_code="query_invalid_argument",
            category="invalid_argument",
            provider_code=3,
            retryable=False,
            suggested_action="check_query_arguments",
        )

    monkeypatch.setattr(chat_tools.chat_service, "query", rejected_query)

    result = await chat_tools.notebook_query("nb-123", "question")

    assert result["status"] == "error"
    assert result["error"] == "The query request is invalid."
    assert result["hint"] == "Check the source IDs."
    assert result["error_details"] == {
        "category": "invalid_argument",
        "provider_code": 3,
        "retryable": False,
        "suggested_action": "check_query_arguments",
        "debug_code": "query_invalid_argument",
    }


@pytest.mark.asyncio
async def test_notebook_query_accepts_string_source_ids_at_mcp_boundary(monkeypatch):
    from notebooklm_tools.mcp.server import mcp

    seen = {}

    def query(*args, **kwargs):
        seen.update(kwargs)
        return {"answer": "ok"}

    monkeypatch.setattr(chat_tools, "get_client", lambda: object())
    monkeypatch.setattr(chat_tools.chat_service, "query", query)

    result = await mcp.call_tool(
        "notebook_query",
        {"notebook_id": "nb-123", "query": "question", "source_ids": "src-1,src-2"},
    )

    assert result.structured_content == {"status": "success", "answer": "ok"}
    assert seen["source_ids"] == ["src-1", "src-2"]
