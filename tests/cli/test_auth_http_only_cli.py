"""CLI HTTP-only mode invokes no browser and respects the selected profile."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from typer.testing import CliRunner

from notebooklm_tools.cli.main import app
from notebooklm_tools.services import auth_http
from notebooklm_tools.services.errors import ServiceError


def test_http_only_invokes_http_refresh_not_browser(monkeypatch):
    monkeypatch.delenv("NOTEBOOKLM_COOKIES", raising=False)
    monkeypatch.setenv("NOTEBOOKLM_DISABLE_HEADLESS_REFRESH", "1")
    refresh = Mock(return_value=SimpleNamespace())
    browser = Mock()
    monkeypatch.setattr(auth_http, "refresh_auth_http_only", refresh)
    monkeypatch.setattr("notebooklm_tools.utils.auth_browser.run_headless_auth", browser)
    result = CliRunner().invoke(app, ["auth", "refresh", "--http-only", "--profile", "secondary"])
    assert result.exit_code == 0, result.output
    refresh.assert_called_once_with("secondary")
    browser.assert_not_called()


def test_http_only_failure_exits_nonzero(monkeypatch):
    monkeypatch.delenv("NOTEBOOKLM_COOKIES", raising=False)
    monkeypatch.setattr(
        auth_http,
        "refresh_auth_http_only",
        Mock(side_effect=ServiceError("stale Google login")),
    )
    result = CliRunner().invoke(app, ["auth", "refresh", "--http-only", "--profile", "secondary"])
    assert result.exit_code == 1
    assert "stale Google login" in result.output
