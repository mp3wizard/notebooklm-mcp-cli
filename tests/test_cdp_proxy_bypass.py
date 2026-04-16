"""CDP WebSocket must not use HTTP*_PROXY for localhost (Issue #119, PR #157)."""

import os
from unittest.mock import MagicMock, patch


def test_cdp_websocket_without_proxy_env_strips_and_restores(monkeypatch):
    from notebooklm_tools.utils.cdp import _cdp_websocket_without_proxy_env

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:2")

    with _cdp_websocket_without_proxy_env():
        assert "HTTP_PROXY" not in os.environ
        assert "HTTPS_PROXY" not in os.environ

    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:1"
    assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:2"


def test_execute_cdp_command_creates_ws_without_proxy_env(monkeypatch):
    import notebooklm_tools.utils.cdp as cdp_mod
    from notebooklm_tools.utils.cdp import execute_cdp_command

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")

    cdp_mod._cached_ws = None
    cdp_mod._cached_ws_url = None

    seen: dict[str, bool] = {}

    ws_mock = MagicMock()

    def fake_create_connection(url, timeout=None, **kwargs):
        seen["http_proxy_set"] = "HTTP_PROXY" in os.environ
        seen["https_proxy_set"] = "HTTPS_PROXY" in os.environ
        return ws_mock

    ws_mock.recv.return_value = '{"id": 1, "result": {}}'

    with patch.object(cdp_mod.websocket, "create_connection", side_effect=fake_create_connection):
        execute_cdp_command(
            "ws://127.0.0.1:9222/devtools/page/fake",
            "Runtime.enable",
            retry=False,
        )

    assert seen["http_proxy_set"] is False
    assert seen["https_proxy_set"] is False
    assert os.environ.get("HTTP_PROXY") == "http://127.0.0.1:9"
    assert os.environ.get("HTTPS_PROXY") == "http://127.0.0.1:9"

    cdp_mod._cached_ws = None
    cdp_mod._cached_ws_url = None
