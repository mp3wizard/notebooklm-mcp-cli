"""_call_rpc must be able to skip 5xx replays for non-idempotent kickoffs."""

from unittest.mock import MagicMock

import httpx
import pytest

from notebooklm_tools.core.base import BaseClient


def _client_returning(status_code: int) -> BaseClient:
    client = BaseClient(cookies={"SID": "x"}, csrf_token="t")
    request = httpx.Request("POST", "https://notebook.google.com/x")
    response = httpx.Response(status_code, request=request, text="err")
    http = MagicMock()
    http.post.return_value = response
    client._get_client = MagicMock(return_value=http)
    client._cdp_rpc_transport_enabled = MagicMock(return_value=False)
    return client


def test_server_error_is_not_replayed_when_disabled(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    client = _client_returning(502)
    with pytest.raises(httpx.HTTPStatusError):
        client._call_rpc("Rytqqe", [], "/notebook/nb", retry_server_errors=False)
    assert client._get_client.return_value.post.call_count == 1


def test_server_error_is_replayed_by_default(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    client = _client_returning(502)
    with pytest.raises(httpx.HTTPStatusError):
        client._call_rpc("wXbhsf", [], "/")
    assert client._get_client.return_value.post.call_count > 1
