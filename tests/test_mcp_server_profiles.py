from unittest.mock import patch

import pytest

from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.core.credential_store import CredentialStore
from notebooklm_tools.mcp.tools.server import server_info
from notebooklm_tools.services.auth_storage import set_storage_mode
from notebooklm_tools.utils import config as cfg


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch, fake_credential_store):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / "storage"))
    for var in ("NLM_PROFILE", "NOTEBOOKLM_COOKIES", "NLM_AUTH_STORAGE"):
        monkeypatch.delenv(var, raising=False)
    cfg.set_session_profile(None)
    AuthManager("default").save_profile(cookies={"SID": "d"}, email="d@example.com")
    AuthManager("work").save_profile(cookies={"SID": "w"}, email="w@example.com")
    set_storage_mode(mode="protected", profile_name="work")
    yield
    cfg.set_session_profile(None)


def _info():
    with (
        patch("notebooklm_tools.mcp.tools.server._get_latest_pypi_version", return_value=None),
        patch("notebooklm_tools.mcp.tools.server._check_auth_status", return_value="configured"),
    ):
        return server_info()


def test_server_info_lists_profiles_with_modes_and_active():
    info = _info()
    rows = {p["name"]: p for p in info["profiles"]}
    assert rows["work"]["storage_mode"] == "protected"
    assert rows["default"]["email"] == "d@example.com"
    assert rows["default"]["has_conflict"] is False
    assert info["active_profile"]["profile"] == "default"


def test_server_info_profile_section_never_touches_keystore(monkeypatch):
    def no_keystore(*a, **k):
        raise AssertionError("keystore touched")

    for meth in ("read_credentials", "is_available", "write_credentials"):
        monkeypatch.setattr(CredentialStore, meth, no_keystore)
    assert _info()["status"] == "success"


def test_server_info_has_no_secrets():
    assert "SID" not in repr(_info()["profiles"])
