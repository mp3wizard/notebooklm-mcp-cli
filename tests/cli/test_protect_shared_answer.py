"""Tests for shared protect answer across wizard and login, and fresh explicit probe."""

import pytest
from typer.testing import CliRunner

from notebooklm_tools.cli.commands.setup_wizard import _check_wizard_protect_prompt
from notebooklm_tools.cli.main import _maybe_prompt_protect_mode, app
from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.core.credential_store import CredentialStore
from notebooklm_tools.core.notices import (
    cache_probe_result,
    get_cached_probe_result,
    get_protect_answer,
    record_protect_answer,
)
from notebooklm_tools.services.auth_storage import get_storage_status
from notebooklm_tools.utils.config import reset_config

runner = CliRunner()


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch, fake_credential_store):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path))
    reset_config()
    yield
    reset_config()


def test_shared_answer_wizard_then_login(monkeypatch, fake_credential_store):
    """User answers 'No' in wizard -> post-login does not ask again."""
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "sid"}, email="user@example.com")

    # Record answer in wizard as "no"
    record_protect_answer("default", "no")

    # Post-login prompt must not ask
    asked = False

    def _mock_confirm(*args, **kwargs):
        nonlocal asked
        asked = True
        return False

    import typer

    monkeypatch.setattr(typer, "confirm", _mock_confirm)

    _maybe_prompt_protect_mode("default")
    assert not asked
    assert get_protect_answer("default") == "no"
    assert get_storage_status("default")["mode"] == "file"


def test_shared_answer_login_then_wizard(monkeypatch, fake_credential_store):
    """User answers 'No' in post-login -> wizard does not ask again."""
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "sid"}, email="user@example.com")

    # Simulate post-login answering "no"
    record_protect_answer("default", "no")

    # In wizard, prompt should not run
    asked = False

    class _MockQuestionaryConfirm:
        def ask(self):
            nonlocal asked
            asked = True
            return False

    import questionary

    monkeypatch.setattr(questionary, "confirm", lambda *args, **kwargs: _MockQuestionaryConfirm())

    _check_wizard_protect_prompt()
    assert not asked
    assert get_protect_answer("default") == "no"


def test_failed_cached_probe_does_not_block_explicit_set_protected(
    monkeypatch, fake_credential_store
):
    """A probe that previously failed and was cached does not block an explicit set protected that works."""
    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "sid"}, email="user@example.com")

    # Cache probe as unavailable (e.g. from an invite check 2 weeks ago)
    cache_probe_result(False)
    assert get_cached_probe_result() is False

    # should_offer_protection obeys the cache
    store = CredentialStore()
    assert store.should_offer_protection() is False

    # But is_available() is always a fresh probe!
    assert store.is_available() is True

    # Explicit set protected succeeds!
    res = runner.invoke(app, ["auth", "storage", "set", "protected"], input="\n")
    assert res.exit_code == 0
    assert "Storage mode set to 'protected'" in res.output

    # Successful explicit set protected updates the cached probe to available
    assert get_cached_probe_result() is True
    assert get_protect_answer("default") == "yes"


def test_wizard_reports_failed_protect_instead_of_hiding_it(monkeypatch, capsys, pretend_desktop):
    """Wizard 'Yes' + failed switch must print the error, not swallow it."""
    import notebooklm_tools.cli.commands.setup_wizard as wizard

    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "sid"}, email="user@example.com")

    class _Answer:
        def ask(self):
            return True

    def _fail(*args, **kwargs):
        raise RuntimeError("keystore locked")

    monkeypatch.setattr(wizard, "is_interactive", lambda: True)
    monkeypatch.setattr(wizard.questionary, "confirm", lambda *a, **k: _Answer())
    monkeypatch.setattr("notebooklm_tools.services.auth_storage.set_storage_mode", _fail)

    _check_wizard_protect_prompt()

    out = capsys.readouterr().out
    assert "Could not enable protected mode" in out
    assert "keystore locked" in out
    assert get_storage_status("default")["mode"] == "file"
