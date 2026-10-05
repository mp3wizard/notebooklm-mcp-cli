"""A cancelled or failed browser login must close the automation Chrome it launched."""

import pytest
import typer
from typer.testing import CliRunner

from notebooklm_tools.cli import main
from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.core.exceptions import NLMError
from notebooklm_tools.utils.config import get_profile_dir, reset_config

ST = "notebooklm_tools.services.auth_storage"


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch, fake_credential_store):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / "storage"))
    monkeypatch.delenv("NLM_AUTH_STORAGE", raising=False)
    reset_config()
    monkeypatch.setattr(main, "_is_terminal", lambda: True)
    monkeypatch.setattr(f"{ST}.is_desktop_session", lambda: True)
    monkeypatch.setattr(f"{ST}.keystore_available", lambda: True)
    monkeypatch.setattr(typer, "prompt", lambda *a, **k: 1)
    monkeypatch.setattr("notebooklm_tools.utils.cdp.get_chrome_path", lambda: "chrome")
    monkeypatch.setattr("notebooklm_tools.utils.cdp.get_browser_display_name", lambda: "Chrome")
    monkeypatch.setattr(
        "notebooklm_tools.utils.config.check_migration_sources",
        lambda: {"chrome_profiles": []},
    )
    yield
    reset_config()


@pytest.fixture
def closed(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "notebooklm_tools.utils.cdp.terminate_chrome", lambda *a, **k: calls.append(1) or True
    )
    return calls


def test_ctrl_c_during_sign_in_closes_chrome_and_exits_130(monkeypatch, closed):
    def interrupted(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("notebooklm_tools.utils.cdp.extract_cookies_via_cdp", interrupted)
    result = CliRunner().invoke(main.app, ["login", "--profile", "work"])
    assert result.exit_code == 130
    assert closed == [1]
    assert "cancelled" in result.output.lower()
    assert "work" not in AuthManager.list_profiles()
    assert not get_profile_dir("work", create=False).exists()


def test_failed_login_also_closes_chrome(monkeypatch, closed):
    def timed_out(**kwargs):
        raise NLMError("Login timed out")

    monkeypatch.setattr("notebooklm_tools.utils.cdp.extract_cookies_via_cdp", timed_out)
    result = CliRunner().invoke(main.app, ["login", "--profile", "work"])
    assert result.exit_code == 1
    assert closed == [1]
