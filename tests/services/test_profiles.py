"""Profile listing and switching for MCP clients that cannot run the CLI."""

import pytest

from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.core.credential_store import CredentialStore
from notebooklm_tools.services import profiles
from notebooklm_tools.services.auth_storage import set_storage_mode
from notebooklm_tools.services.errors import NotFoundError, ServiceError
from notebooklm_tools.utils import config as cfg


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch, fake_credential_store):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / "storage"))
    for var in ("NLM_PROFILE", "NOTEBOOKLM_COOKIES", "NLM_AUTH_STORAGE"):
        monkeypatch.delenv(var, raising=False)
    cfg.set_session_profile(None)
    AuthManager("default").save_profile(cookies={"SID": "d"}, email="d@example.com")
    AuthManager("work").save_profile(cookies={"SID": "w"}, email="w@example.com")
    yield
    cfg.set_session_profile(None)


def test_list_marks_saved_default_and_active():
    rows = {r["name"]: r for r in profiles.list_profiles()}
    assert rows["default"]["is_saved_default"] and rows["default"]["is_active"]
    assert not rows["work"]["is_active"]
    assert rows["work"]["email"] == "w@example.com"
    assert rows["work"]["storage_mode"] == "file"


def test_list_never_opens_the_keystore_even_for_protected(monkeypatch):
    set_storage_mode(mode="protected", profile_name="work")

    def no_keystore(*a, **k):
        raise AssertionError("keystore touched")

    monkeypatch.setattr(CredentialStore, "read_credentials", no_keystore)
    monkeypatch.setattr(CredentialStore, "is_available", no_keystore)
    rows = {r["name"]: r for r in profiles.list_profiles()}
    assert rows["work"]["email"] == "w@example.com"
    assert rows["work"]["storage_mode"] == "protected"


def test_list_never_contains_secrets_or_ghosts():
    cfg.set_auth_storage_mode("ghost", "protected")
    rows = profiles.list_profiles()
    assert "ghost" not in {r["name"] for r in rows}
    assert "SID" not in repr(rows) and "cookies" not in repr(rows)


def test_session_switch_changes_active_but_not_saved_default():
    out = profiles.switch_session_profile("work")
    assert out["scope"] == "session"
    active = profiles.get_active_profile()
    assert active == {"profile": "work", "source": "session", "saved_default": "default"}


def test_switch_to_unknown_or_ghost_profile_errors_and_keeps_active():
    cfg.set_auth_storage_mode("ghost", "protected")
    for bad in ("nope", "ghost"):
        with pytest.raises(NotFoundError) as exc:
            profiles.switch_session_profile(bad)
        assert "default" in str(exc.value) and "work" in str(exc.value)
        assert "ghost" not in str(exc.value).split("Available profiles:")[1]
    assert profiles.get_active_profile()["profile"] == "default"


def test_switch_refused_when_env_cookies_pin_the_account(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_COOKIES", "SID=env")
    with pytest.raises(ServiceError, match="NOTEBOOKLM_COOKIES"):
        profiles.switch_session_profile("work")
    with pytest.raises(ServiceError, match="NOTEBOOKLM_COOKIES"):
        profiles.make_default_profile("work")
    assert profiles.get_active_profile()["source"] == "env cookies"


def test_make_default_writes_saved_default_and_activates():
    out = profiles.make_default_profile("work")
    assert out["scope"] == "saved default"
    assert cfg.get_saved_default_profile() == "work"
    assert profiles.get_active_profile() == {
        "profile": "work",
        "source": "saved default",
        "saved_default": "work",
    }


def test_make_default_after_session_switch_persists_the_requested_one():
    profiles.switch_session_profile("work")
    profiles.make_default_profile("default")
    assert cfg.get_saved_default_profile() == "default"
    assert profiles.get_active_profile()["profile"] == "default"


def test_make_default_refuses_when_env_pins_profile(monkeypatch):
    monkeypatch.setenv("NLM_PROFILE", "default")
    cfg.reset_config()
    with pytest.raises(ServiceError, match="NLM_PROFILE"):
        profiles.make_default_profile("work")
    assert cfg.get_saved_default_profile() == "default"


def test_storage_status_is_metadata_only(monkeypatch):
    def no_keystore(*a, **k):
        raise AssertionError("keystore touched")

    set_storage_mode(mode="protected", profile_name="work")
    monkeypatch.setattr(CredentialStore, "read_credentials", no_keystore)
    status = profiles.profile_storage_status("work")
    assert status["mode"] == "protected"
    assert "SID" not in repr(status)
