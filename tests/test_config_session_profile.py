"""Session profile override: followed for account selection, never for the saved-default mirror."""

import json

import pytest

from notebooklm_tools.core.auth import AuthManager, AuthTokens, save_tokens_to_cache
from notebooklm_tools.utils import config as cfg


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / "storage"))
    monkeypatch.delenv("NLM_PROFILE", raising=False)
    monkeypatch.delenv("NLM_AUTH_STORAGE", raising=False)
    cfg.set_session_profile(None)
    yield
    cfg.set_session_profile(None)


def test_override_changes_default_profile_everywhere():
    assert cfg.get_config().auth.default_profile == "default"
    cfg.set_session_profile("work")
    assert cfg.get_config().auth.default_profile == "work"
    assert cfg.get_session_profile() == "work"


def test_clearing_override_returns_to_saved_default():
    cfg.set_session_profile("work")
    cfg.set_session_profile(None)
    assert cfg.get_config().auth.default_profile == "default"


def test_override_beats_env(monkeypatch):
    monkeypatch.setenv("NLM_PROFILE", "from-env")
    cfg.reset_config()
    cfg.set_session_profile("work")
    assert cfg.get_config().auth.default_profile == "work"
    assert cfg.get_base_default_profile() == "from-env"


def test_save_config_never_persists_the_session_override():
    cfg.set_session_profile("work")
    cfg.save_config(cfg.get_config())
    assert cfg.get_saved_default_profile() == "default"


def test_saved_default_reads_file_only():
    c = cfg.get_config()
    c.auth.default_profile = "personal"
    cfg.save_config(c)
    cfg.reset_config()
    cfg.set_session_profile("work")
    assert cfg.get_saved_default_profile() == "personal"
    assert cfg.get_base_default_profile() == "personal"


def test_root_mirror_ignores_session_override():
    AuthManager("default").save_profile(cookies={"SID": "d"}, email="d@example.com")
    AuthManager("work").save_profile(cookies={"SID": "w"}, email="w@example.com")
    cfg.set_session_profile("work")
    save_tokens_to_cache(AuthTokens(cookies={"SID": "w2"}), silent=True, profile_name="work")
    root = cfg.get_storage_dir() / "auth.json"
    assert not root.exists() or json.loads(root.read_text())["cookies"] != {"SID": "w2"}
    save_tokens_to_cache(AuthTokens(cookies={"SID": "d2"}), silent=True, profile_name="default")
    assert json.loads(root.read_text())["cookies"] == {"SID": "d2"}
