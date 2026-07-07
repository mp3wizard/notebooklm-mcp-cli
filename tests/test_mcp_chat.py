"""Tests for MCP chat tool wrappers."""

import asyncio
import inspect
import threading
import time

import pytest

from notebooklm_tools.mcp.tools import chat as chat_tools


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
