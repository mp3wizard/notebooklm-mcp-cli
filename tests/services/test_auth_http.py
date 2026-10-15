"""HTTP-only refresh never launches a browser and never persists unvalidated cookies."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from notebooklm_tools.core.client import NotebookLMClient
from notebooklm_tools.services import auth_http
from notebooklm_tools.services.errors import NotFoundError, ServiceError


def _cached():
    return SimpleNamespace(
        cookies={"SID": "old"},
        csrf_token="old",
        session_id="old-sid",
        build_label="old-bl",
        base_host="notebooklm.google.com",
        revision=None,
    )


class FakeClient:
    fail = False

    def __init__(self, **kwargs):
        self.profile_name = kwargs["profile_name"]
        self.is_env_auth = kwargs["is_env_auth"]
        self.cookies = {"SID": "new"}
        self.csrf_token = "new-csrf"
        self._session_id = "new-sid"
        self._bl = "new-bl"
        self._base_host = "notebooklm.google.com"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def _refresh_auth_tokens(self):
        if self.fail:
            raise ValueError("Google redirected to login")

    def list_notebooks(self, *, require_valid_response=False):
        assert require_valid_response
        return []


def test_http_refresh_validates_before_persist(monkeypatch):
    saved = Mock(return_value="rev-new")
    monkeypatch.setattr(auth_http, "load_cached_tokens", lambda **_: _cached())
    monkeypatch.setattr(auth_http, "save_tokens_to_cache", saved)
    monkeypatch.setattr(auth_http, "NotebookLMClient", FakeClient)
    refreshed = auth_http.refresh_auth_http_only("secondary")
    assert refreshed == {"profile": "secondary", "status": "success"}
    assert saved.call_args.args[0].csrf_token == "new-csrf"
    assert saved.call_args.kwargs["profile_name"] == "secondary"
    assert saved.call_args.kwargs["force"] is False


def test_http_refresh_never_persists_rejected_credentials(monkeypatch):
    class RejectedClient(FakeClient):
        fail = True

    saved = Mock()
    monkeypatch.setattr(auth_http, "load_cached_tokens", lambda **_: _cached())
    monkeypatch.setattr(auth_http, "save_tokens_to_cache", saved)
    monkeypatch.setattr(auth_http, "NotebookLMClient", RejectedClient)
    with pytest.raises(ServiceError, match="Could not validate"):
        auth_http.refresh_auth_http_only("secondary")
    saved.assert_not_called()


def test_http_refresh_requires_saved_profile(monkeypatch):
    monkeypatch.setattr(auth_http, "load_cached_tokens", lambda **_: None)
    with pytest.raises(NotFoundError, match="No saved"):
        auth_http.refresh_auth_http_only("missing")


@pytest.mark.parametrize("csrf", ["", "cached"])
@pytest.mark.parametrize("payload", ["[]", None, '"malformed"'])
def test_real_http_client_rejects_missing_payload_without_browser(monkeypatch, csrf, payload):
    cached = _cached()
    cached.csrf_token = csrf
    monkeypatch.setenv("NOTEBOOKLM_RPC_TRANSPORT", "cdp")
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", "https://notebook.google.com")
    monkeypatch.setattr(auth_http, "load_cached_tokens", lambda **_: cached)
    saved = Mock()
    monkeypatch.setattr(auth_http, "save_tokens_to_cache", saved)
    browser = Mock(side_effect=AssertionError("HTTP-only must not open a browser"))
    monkeypatch.setattr(NotebookLMClient, "_prepare_cdp_transport", browser)
    monkeypatch.setattr(NotebookLMClient, "_refresh_auth_tokens", Mock())

    def post(url, **kwargs):
        body = (
            "not an RPC response"
            if payload is None
            else '[["wrb.fr", "'
            + NotebookLMClient.RPC_LIST_NOTEBOOKS
            + '", '
            + json.dumps(payload)
            + "]]"
        )
        return httpx.Response(200, text=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(NotebookLMClient, "_get_client", lambda self: Mock(post=post))
    if payload == "[]":
        assert auth_http.refresh_auth_http_only("secondary")["status"] == "success"
        saved.assert_called_once()
    else:
        with pytest.raises(ServiceError):
            auth_http.refresh_auth_http_only("secondary")
        saved.assert_not_called()
    browser.assert_not_called()
    assert os.environ["NOTEBOOKLM_RPC_TRANSPORT"] == "cdp"
