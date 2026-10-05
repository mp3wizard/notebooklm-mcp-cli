"""MCP profile tool: list, status, switch (this server process), optional make-default."""

import pytest

from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.mcp.tools import _utils, profiles
from notebooklm_tools.utils import config as cfg


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch, fake_credential_store):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / "storage"))
    for var in ("NLM_PROFILE", "NOTEBOOKLM_COOKIES", "NLM_AUTH_STORAGE"):
        monkeypatch.delenv(var, raising=False)
    cfg.set_session_profile(None)
    # csrf/session present, so building a client never needs the network
    AuthManager("default").save_profile(
        cookies={"SID": "d"}, csrf_token="c", session_id="s", email="d@example.com"
    )
    AuthManager("work").save_profile(
        cookies={"SID": "w"}, csrf_token="c", session_id="s", email="w@example.com"
    )
    monkeypatch.setattr(_utils, "_client", None)
    yield
    cfg.set_session_profile(None)


def test_list_returns_profiles_and_active():
    out = profiles.profile(action="list")
    assert out["status"] == "success"
    assert {p["name"] for p in out["profiles"]} == {"default", "work"}
    assert out["active"]["profile"] == "default"


def test_switch_is_session_only_by_default():
    out = profiles.profile(action="switch", name="work")
    assert out["status"] == "success" and out["scope"] == "session"
    assert cfg.get_saved_default_profile() == "default"
    assert profiles.profile(action="list")["active"]["profile"] == "work"


def test_switch_with_make_default_persists():
    out = profiles.profile(action="switch", name="work", make_default=True)
    assert out["scope"] == "saved default"
    assert cfg.get_saved_default_profile() == "work"


def test_switch_unknown_profile_is_an_error():
    out = profiles.profile(action="switch", name="nope")
    assert out["status"] == "error" and "nope" in out["error"]


def test_switch_requires_name():
    assert profiles.profile(action="switch")["status"] == "error"


def test_switch_refused_with_env_cookies(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_COOKIES", "SID=env")
    out = profiles.profile(action="switch", name="work")
    assert out["status"] == "error" and "NOTEBOOKLM_COOKIES" in out["error"]


def test_unknown_action_is_rejected():
    assert profiles.profile(action="delete", name="work")["status"] == "error"


def test_status_returns_metadata_only():
    out = profiles.profile(action="status", name="work")
    assert out["status"] == "success"
    assert out["storage"]["mode"] == "file"
    assert "SID" not in repr(out)


def test_get_client_follows_the_session_switch():
    assert _utils.get_client()._profile_name == "default"
    profiles.profile(action="switch", name="work")
    assert _utils.get_client()._profile_name == "work"
