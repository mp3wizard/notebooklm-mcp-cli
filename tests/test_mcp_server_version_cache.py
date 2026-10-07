"""Tests for MCP server-info PyPI version caching."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from notebooklm_tools.mcp.tools import server


@pytest.fixture(autouse=True)
def reset_version_cache(monkeypatch):
    monkeypatch.setattr(server, "_version_cache", None)


def test_successful_version_lookup_is_cached(monkeypatch):
    calls = 0

    def fetch():
        nonlocal calls
        calls += 1
        return "9.9.9"

    monkeypatch.setattr(server, "_fetch_latest_pypi_version", fetch)

    assert server._get_latest_pypi_version() == "9.9.9"
    assert server._get_latest_pypi_version() == "9.9.9"
    assert calls == 1


def test_failed_lookup_uses_short_negative_cache(monkeypatch):
    calls = 0
    clock = iter([100.0, 100.0, 120.0, 401.0, 401.0])

    def fetch():
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(server, "_fetch_latest_pypi_version", fetch)
    monkeypatch.setattr(server.time, "monotonic", lambda: next(clock))

    assert server._get_latest_pypi_version() is None
    assert server._get_latest_pypi_version() is None
    assert server._get_latest_pypi_version() is None
    assert calls == 2


def test_success_cache_expires_after_ttl(monkeypatch):
    values = iter(["1.0.0", "2.0.0"])
    clock = iter([100.0, 100.0, 200.0, 86601.0, 86601.0])

    monkeypatch.setattr(server, "_fetch_latest_pypi_version", lambda: next(values))
    monkeypatch.setattr(server.time, "monotonic", lambda: next(clock))

    assert server._get_latest_pypi_version() == "1.0.0"
    assert server._get_latest_pypi_version() == "1.0.0"
    assert server._get_latest_pypi_version() == "2.0.0"


def test_concurrent_calls_share_one_network_fetch(monkeypatch):
    calls = 0
    calls_lock = threading.Lock()

    def fetch():
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.05)
        return "3.0.0"

    monkeypatch.setattr(server, "_fetch_latest_pypi_version", fetch)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _index: server._get_latest_pypi_version(), range(8)))

    assert results == ["3.0.0"] * 8
    assert calls == 1
