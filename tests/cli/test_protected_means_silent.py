"""A protected profile never triggers any protection tip, notice or prompt."""

import sys
import threading

import pytest

from notebooklm_tools.cli import main
from notebooklm_tools.cli.commands import setup_wizard
from notebooklm_tools.cli.utils import print_storage_mode_notification
from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.core.notices import record_protect_answer
from notebooklm_tools.mcp.tools import _utils
from notebooklm_tools.services.auth_storage import set_storage_mode
from notebooklm_tools.utils.config import reset_config


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch, fake_credential_store):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / "storage"))
    monkeypatch.delenv("NLM_AUTH_STORAGE", raising=False)
    reset_config()
    AuthManager("default").save_profile(cookies={"SID": "d"}, email="d@example.com")
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        monkeypatch.setattr(stream, "isatty", lambda: True)
    done = threading.Event()
    done.set()
    monkeypatch.setattr(_utils, "_mcp_probe_event", done)
    monkeypatch.setattr(_utils, "_mcp_probe_available", True)
    yield
    reset_config()


def _protect_default():
    set_storage_mode(mode="protected", profile_name="default")


def test_mcp_notice_fires_for_plain_profile():
    """Control: proves the gate is real (the probe says yes, profile is plain)."""
    result = {"status": "success"}
    _utils.maybe_attach_mcp_notice(result)
    assert "user_notice" in result


def test_mcp_notice_never_attached_for_protected_profile():
    _protect_default()
    result = {"status": "success"}
    _utils.maybe_attach_mcp_notice(result)
    assert "user_notice" not in result


def test_mcp_notice_never_attached_when_user_already_answered():
    record_protect_answer("default", "no")
    result = {"status": "success"}
    _utils.maybe_attach_mcp_notice(result)
    assert "user_notice" not in result


def test_cli_tip_is_silent_for_protected(capsys):
    _protect_default()
    print_storage_mode_notification()
    out = capsys.readouterr()
    assert "protect" not in (out.out + out.err).lower()


def test_wizard_startup_prompt_is_silent_for_protected(monkeypatch):
    _protect_default()
    monkeypatch.setattr(
        setup_wizard.questionary, "confirm", lambda *a, **k: pytest.fail("must not ask")
    )
    monkeypatch.setattr(setup_wizard, "is_interactive", lambda: True)
    setup_wizard._check_wizard_protect_prompt()


def test_after_login_question_is_silent_for_protected(monkeypatch):
    import typer

    _protect_default()
    monkeypatch.setattr(typer, "confirm", lambda *a, **k: pytest.fail("must not ask"))
    main._maybe_prompt_protect_mode("default")
