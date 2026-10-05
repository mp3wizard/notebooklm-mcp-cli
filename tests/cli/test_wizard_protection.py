"""Wizard 'Credential protection' door (keystore faked; no real prompts)."""

import pytest

from notebooklm_tools.cli.commands import setup_wizard
from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.core.notices import get_protect_answer
from notebooklm_tools.services.auth_storage import set_storage_mode
from notebooklm_tools.utils.config import get_auth_storage_mode, reset_config

PROTECT = "Protect saved logins (recommended)"
RESTORE = "Restore protected logins to plain files"


class _Answer:
    def __init__(self, value):
        self.value = value

    def ask(self):
        return self.value


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch, fake_credential_store):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / "storage"))
    monkeypatch.delenv("NLM_AUTH_STORAGE", raising=False)
    reset_config()
    yield
    reset_config()


def _save(*names):
    for n in names:
        AuthManager(n).save_profile(cookies={"SID": n}, email=f"{n}@example.com")


def _script(monkeypatch, *, menu_choice, confirm=True, picked=None):
    """Feed the door: one select answer, one confirm answer, one picker answer."""
    seen = {}

    def fake_select(prompt, choices, **kw):
        seen["choices"] = list(choices)
        return _Answer(menu_choice)

    monkeypatch.setattr(setup_wizard.questionary, "select", fake_select)
    monkeypatch.setattr(setup_wizard.questionary, "confirm", lambda *a, **k: _Answer(confirm))
    monkeypatch.setattr(setup_wizard, "ask_with_back", lambda q: q.ask())
    monkeypatch.setattr(
        "notebooklm_tools.cli.protection_flow.pick_profiles_for_mode",
        lambda profiles, mode, modes: picked,
    )
    monkeypatch.setattr("notebooklm_tools.services.auth_storage.keystore_available", lambda: True)
    return seen


def test_no_profiles_prints_hint(capsys):
    assert setup_wizard._flow_credential_protection() == 0
    assert "No saved logins yet" in capsys.readouterr().out


def test_env_pinned_mode_changes_nothing(monkeypatch, capsys):
    _save("default")
    monkeypatch.setenv("NLM_AUTH_STORAGE", "file")
    setup_wizard._flow_credential_protection()
    assert "pinned by NLM_AUTH_STORAGE" in capsys.readouterr().out


def test_only_protect_offered_when_all_plain(monkeypatch):
    _save("default")
    seen = _script(monkeypatch, menu_choice="Back")
    setup_wizard._flow_credential_protection()
    assert seen["choices"] == [PROTECT, "Back"]


def test_only_restore_offered_when_all_protected(monkeypatch):
    _save("default")
    set_storage_mode(mode="protected", profile_name="default")
    seen = _script(monkeypatch, menu_choice="Back")
    setup_wizard._flow_credential_protection()
    assert seen["choices"] == [RESTORE, "Back"]


def test_both_offered_when_mixed(monkeypatch):
    _save("a", "b")
    set_storage_mode(mode="protected", profile_name="a")
    seen = _script(monkeypatch, menu_choice="Back")
    setup_wizard._flow_credential_protection()
    assert seen["choices"] == [PROTECT, RESTORE, "Back"]


def test_protect_single_profile_switches_and_records_yes(monkeypatch):
    _save("default")
    _script(monkeypatch, menu_choice=PROTECT, confirm=True)
    setup_wizard._flow_credential_protection()
    assert get_auth_storage_mode("default") == "protected"
    assert get_protect_answer("default") == "yes"


def test_protect_declined_changes_nothing(monkeypatch):
    _save("default")
    _script(monkeypatch, menu_choice=PROTECT, confirm=False)
    setup_wizard._flow_credential_protection()
    assert get_auth_storage_mode("default") == "file"
    assert get_protect_answer("default") is None


def test_protect_several_uses_picker_selection(monkeypatch):
    _save("a", "b")
    _script(monkeypatch, menu_choice=PROTECT, picked=["b"])
    setup_wizard._flow_credential_protection()
    assert get_auth_storage_mode("a") == "file"
    assert get_auth_storage_mode("b") == "protected"


def test_picker_esc_changes_nothing(monkeypatch):
    _save("a", "b")
    _script(monkeypatch, menu_choice=PROTECT, picked=None)
    setup_wizard._flow_credential_protection()
    assert get_auth_storage_mode("a") == get_auth_storage_mode("b") == "file"


def test_restore_returns_profile_to_plain_and_records_no(monkeypatch):
    _save("default")
    set_storage_mode(mode="protected", profile_name="default")
    _script(monkeypatch, menu_choice=RESTORE, confirm=True)
    setup_wizard._flow_credential_protection()
    assert get_auth_storage_mode("default") == "file"
    assert get_protect_answer("default") == "no"


def test_unavailable_keystore_changes_nothing(monkeypatch, capsys):
    _save("default")
    _script(monkeypatch, menu_choice=PROTECT)
    monkeypatch.setattr("notebooklm_tools.services.auth_storage.keystore_available", lambda: False)
    setup_wizard._flow_credential_protection()
    assert get_auth_storage_mode("default") == "file"
    assert "keystore isn't available" in capsys.readouterr().out
