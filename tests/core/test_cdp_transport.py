"""Tests for the experimental CDP RPC transport."""

import json
import urllib.parse
from unittest.mock import patch

from notebooklm_tools.core.base import BaseClient
from notebooklm_tools.core.conversation import ConversationMixin


def _batchexecute_response(rpc_id: str, result: object) -> str:
    return ")]}'\n42\n" + json.dumps(
        [["wrb.fr", rpc_id, json.dumps(result, separators=(",", ":"))]]
    )


def test_call_rpc_uses_cdp_transport_when_enabled(monkeypatch):
    """CDP mode refreshes browser-page tokens before building batchexecute payloads."""
    monkeypatch.setenv("NOTEBOOKLM_RPC_TRANSPORT", "cdp")

    with patch.object(BaseClient, "_refresh_auth_tokens"):
        client = BaseClient(
            cookies={"SID": "old"},
            csrf_token="old-csrf",
            session_id="old-session",
            build_label="old-build",
        )

    def fail_get_client():
        raise AssertionError("httpx client should not be used in CDP transport mode")

    def prepare_cdp_transport(self, timeout):
        assert timeout == 45.0
        self.csrf_token = "live-csrf"
        self._session_id = "live-session"
        self._bl = "live-build"

    captured: dict[str, str] = {}

    def post_form_via_cdp(self, url, body, timeout):
        captured["url"] = url
        captured["body"] = body
        captured["timeout"] = timeout
        return _batchexecute_response(client.RPC_LIST_NOTEBOOKS, ["ok"])

    monkeypatch.setattr(client, "_get_client", fail_get_client)
    monkeypatch.setattr(BaseClient, "_prepare_cdp_transport", prepare_cdp_transport, raising=False)
    monkeypatch.setattr(BaseClient, "_post_form_via_cdp", post_form_via_cdp, raising=False)

    result = client._call_rpc(client.RPC_LIST_NOTEBOOKS, [None, 1, None, [2]], timeout=45.0)

    assert result == ["ok"]
    query_params = urllib.parse.parse_qs(urllib.parse.urlparse(captured["url"]).query)
    assert query_params["f.sid"] == ["live-session"]
    assert query_params["bl"] == ["live-build"]
    body_params = urllib.parse.parse_qs(captured["body"])
    assert body_params["at"] == ["live-csrf"]
    assert captured["timeout"] == 45.0


def test_call_rpc_reuses_existing_cdp_context(monkeypatch):
    """A single client should not relaunch Chrome for every CDP RPC."""
    from notebooklm_tools.core import cdp_transport
    from notebooklm_tools.core.cdp_transport import CdpPageContext

    monkeypatch.setenv("NOTEBOOKLM_RPC_TRANSPORT", "cdp")

    with patch.object(BaseClient, "_refresh_auth_tokens"):
        client = BaseClient(
            cookies={"SID": "old"},
            csrf_token="old-csrf",
            session_id="old-session",
            build_label="old-build",
        )

    context_calls = []

    def fake_get_context(**kwargs):
        context_calls.append(kwargs)
        return CdpPageContext(
            profile_name="default",
            port=9222,
            ws_url="ws://page",
            csrf_token="live-csrf",
            session_id="live-session",
            build_label="live-build",
            launched=True,
        )

    def post_form_via_cdp(self, url, body, timeout):
        return _batchexecute_response(client.RPC_LIST_NOTEBOOKS, ["ok"])

    monkeypatch.setattr(cdp_transport, "get_cdp_page_context", fake_get_context)
    monkeypatch.setattr(BaseClient, "_post_form_via_cdp", post_form_via_cdp)

    client._call_rpc(client.RPC_LIST_NOTEBOOKS, [None, 1, None, [2]], timeout=45.0)
    client._call_rpc(client.RPC_LIST_NOTEBOOKS, [None, 1, None, [2]], timeout=45.0)

    assert len(context_calls) == 1


def test_query_uses_cdp_transport_for_streamed_endpoint(monkeypatch):
    """Notebook chat uses in-page fetch when the CDP transport flag is enabled."""
    monkeypatch.setenv("NOTEBOOKLM_RPC_TRANSPORT", "cdp")

    with patch.object(ConversationMixin, "_refresh_auth_tokens"):
        mixin = ConversationMixin(
            cookies={"SID": "old"},
            csrf_token="old-csrf",
            session_id="old-session",
            build_label="old-build",
        )

    def prepare_cdp_transport(self, timeout):
        assert timeout == 99.0
        self.csrf_token = "live-csrf"
        self._session_id = "live-session"
        self._bl = "live-build"

    captured: dict[str, str | float] = {}

    def post_form_via_cdp(self, url, body, timeout):
        captured["url"] = url
        captured["body"] = body
        captured["timeout"] = timeout
        return "streamed response text"

    monkeypatch.setattr(
        ConversationMixin, "_prepare_cdp_transport", prepare_cdp_transport, raising=False
    )
    monkeypatch.setattr(ConversationMixin, "_post_form_via_cdp", post_form_via_cdp, raising=False)

    with (
        patch.object(mixin, "get_conversation_id", return_value="server-conv"),
        patch.object(
            mixin,
            "_parse_query_response",
            return_value=("Browser answer", {}, None),
        ),
        patch(
            "notebooklm_tools.core.conversation._httpx.Client",
            side_effect=AssertionError("httpx client should not be used in CDP transport mode"),
        ),
    ):
        result = mixin.query(
            "nb-123",
            "What changed?",
            source_ids=["src-1"],
            timeout=99.0,
        )

    assert result["answer"] == "Browser answer"
    assert result["conversation_id"] == "server-conv"
    assert "GenerateFreeFormStreamed" in str(captured["url"])
    query_params = urllib.parse.parse_qs(urllib.parse.urlparse(str(captured["url"])).query)
    assert query_params["f.sid"] == ["live-session"]
    assert query_params["bl"] == ["live-build"]
    body_params = urllib.parse.parse_qs(str(captured["body"]))
    assert body_params["at"] == ["live-csrf"]
    assert captured["timeout"] == 99.0


def test_cdp_fetch_passes_long_response_timeout(monkeypatch):
    """CDP Runtime.evaluate must be able to wait longer than the 30s default."""
    from notebooklm_tools.core.cdp_transport import fetch_form_in_page
    from notebooklm_tools.utils import cdp

    captured: dict[str, object] = {}

    def fake_execute_cdp_command(
        ws_url,
        method,
        params=None,
        *,
        retry=True,
        response_timeout=30,
    ):
        captured["ws_url"] = ws_url
        captured["method"] = method
        captured["params"] = params
        captured["retry"] = retry
        captured["response_timeout"] = response_timeout
        return {"result": {"value": {"status": 200, "text": "ok", "url": "https://example.test"}}}

    monkeypatch.setattr(cdp, "execute_cdp_command", fake_execute_cdp_command)

    result = fetch_form_in_page("ws://page", "https://example.test/rpc", "f.req=x&", timeout=180)

    assert result.status_code == 200
    assert result.text == "ok"
    assert captured["method"] == "Runtime.evaluate"
    assert captured["response_timeout"] == 180
    expression = captured["params"]["expression"]  # type: ignore[index]
    assert "credentials" in expression
    assert "include" in expression
    assert "X-Same-Domain" in expression


def test_close_terminates_cdp_browser_launched_by_client(monkeypatch):
    """BaseClient owns and cleans up only the CDP browser it launched."""
    from notebooklm_tools.core import cdp_transport
    from notebooklm_tools.core.cdp_transport import CdpPageContext
    from notebooklm_tools.utils import cdp

    with patch.object(BaseClient, "_refresh_auth_tokens"):
        client = BaseClient(cookies={"SID": "old"}, csrf_token="old-csrf")

    def fake_get_context(**kwargs):
        return CdpPageContext(
            profile_name="default",
            port=9230,
            ws_url="ws://page",
            csrf_token="live-csrf",
            session_id="live-session",
            build_label="live-build",
            launched=True,
        )

    terminated: list[int] = []
    monkeypatch.setattr(cdp_transport, "get_cdp_page_context", fake_get_context)
    monkeypatch.setattr(cdp, "terminate_chrome", lambda port: terminated.append(port) or True)

    client._prepare_cdp_transport(timeout=5)
    client.close()

    assert terminated == [9230]
    assert client._cdp_launched_port is None
    assert client._cdp_ws_url is None


def test_get_cdp_context_reuses_profile_browser_if_launch_races(monkeypatch):
    """A parallel process may expose the same profile while our launch is still cold."""
    from notebooklm_tools.core.cdp_transport import get_cdp_page_context
    from notebooklm_tools.utils import cdp

    attempts = iter([(None, None), (9230, "ws://browser")])

    monkeypatch.setattr(cdp, "has_chrome_profile", lambda profile: True)
    monkeypatch.setattr(cdp, "find_existing_nlm_chrome", lambda **kwargs: next(attempts))
    monkeypatch.setattr(cdp, "get_debugger_url", lambda *args, **kwargs: None)
    monkeypatch.setattr(cdp, "launch_chrome", lambda **kwargs: True)
    monkeypatch.setattr(
        cdp,
        "find_or_create_notebooklm_page",
        lambda port: {"webSocketDebuggerUrl": f"ws://page-{port}"},
    )
    monkeypatch.setattr(cdp, "_normalize_ws_url", lambda url: url)
    monkeypatch.setattr(cdp, "get_current_url", lambda ws_url: "https://notebooklm.google.com/")
    monkeypatch.setattr(cdp, "is_logged_in", lambda url: True)
    monkeypatch.setattr(
        cdp,
        "_wait_for_page_ready",
        lambda ws_url, timeout: (
            '{"SNlM0e":"live-csrf","FdrFJe":"123","cfb2h":"live-build"}',
            True,
        ),
    )
    monkeypatch.setattr(cdp, "extract_csrf_token", lambda html: "live-csrf")
    monkeypatch.setattr(cdp, "extract_session_id", lambda html: "123")
    monkeypatch.setattr(cdp, "extract_build_label", lambda html: "live-build")

    context = get_cdp_page_context(timeout=1)

    assert context.port == 9230
    assert context.ws_url == "ws://page-9230"
    assert context.session_id == "123"
