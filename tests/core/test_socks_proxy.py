"""Regression tests for outbound SOCKS proxy support (Issue #237)."""

import importlib.metadata

import pytest

from notebooklm_tools.core.base import BaseClient


def _configure_socks_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ALL_PROXY", "socks5h://127.0.0.1:62225")


def test_package_declares_httpx_socks_support() -> None:
    requirements = importlib.metadata.requires("notebooklm-mcp-cli") or []

    assert any(requirement.startswith("httpx[socks]") for requirement in requirements)


def test_sync_client_initializes_with_socks_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_socks_proxy(monkeypatch)
    client = BaseClient(cookies={}, csrf_token="test-token")

    http_client = client._get_client()

    assert http_client is not None
    client.close()


@pytest.mark.asyncio
async def test_async_client_initializes_with_socks_proxy_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_socks_proxy(monkeypatch)
    client = BaseClient(cookies={}, csrf_token="test-token")

    http_client = client._get_async_client()

    assert http_client is not None
    await http_client.aclose()
