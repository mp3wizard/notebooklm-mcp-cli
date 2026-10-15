"""Explicit MCP auth refresh must not switch or replace another account."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from notebooklm_tools.mcp.tools import auth as auth_tools
from notebooklm_tools.services import auth as auth_service
from notebooklm_tools.utils import auth_browser


def test_explicit_profile_refresh_isolated_from_active_client(monkeypatch):
    observed = []
    monkeypatch.delenv("NOTEBOOKLM_COOKIES", raising=False)
    monkeypatch.setattr(
        auth_service,
        "load_cached_tokens",
        lambda **kwargs: (
            observed.append(("load", kwargs)) or SimpleNamespace(cookies={"SID": "old"})
        ),
    )
    monkeypatch.setattr(
        auth_service,
        "credentials_are_usable",
        lambda **kwargs: observed.append(("check", kwargs)) or (True, "configured", None),
    )
    reset = Mock()
    get = Mock()
    monkeypatch.setattr(auth_tools, "reset_client", reset)
    monkeypatch.setattr(auth_tools, "get_client", get)
    monkeypatch.setattr(
        "notebooklm_tools.utils.config.get_config",
        lambda: SimpleNamespace(auth=SimpleNamespace(default_profile="pte")),
    )
    result = auth_tools.refresh_auth(profile="work")
    assert result["status"] == "success"
    assert ("load", {"profile_name": "work"}) in observed
    assert ("check", {"force": True, "profile": "work"}) in observed
    reset.assert_not_called()
    get.assert_not_called()


def test_headless_fallback_uses_explicit_profile(monkeypatch):
    monkeypatch.delenv("NOTEBOOKLM_COOKIES", raising=False)
    monkeypatch.delenv("NOTEBOOKLM_DISABLE_HEADLESS_REFRESH", raising=False)
    monkeypatch.setattr(
        auth_service,
        "load_cached_tokens",
        lambda **kwargs: SimpleNamespace(cookies={"SID": "old"}),
    )
    monkeypatch.setattr(
        auth_service, "credentials_are_usable", lambda **kwargs: (False, "stale", "expired")
    )
    refreshed = Mock(return_value=SimpleNamespace(cookies={"SID": "new"}))
    monkeypatch.setattr(auth_browser, "run_headless_auth", refreshed)
    monkeypatch.setattr(
        "notebooklm_tools.utils.config.get_config",
        lambda: SimpleNamespace(auth=SimpleNamespace(default_profile="pte")),
    )
    reset = Mock()
    monkeypatch.setattr(auth_tools, "reset_client", reset)
    result = auth_tools.refresh_auth(profile="work")
    assert result["status"] == "success"
    assert refreshed.call_args.kwargs["profile_name"] == "work"
    reset.assert_not_called()
