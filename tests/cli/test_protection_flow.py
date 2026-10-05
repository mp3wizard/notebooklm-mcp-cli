"""Shared protection helpers used by `nlm auth storage set` and the setup wizard."""

import pytest

from notebooklm_tools.cli import protection_flow
from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.services.errors import ServiceError
from notebooklm_tools.utils.config import get_profile_dir, reset_config, set_auth_storage_mode


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch, fake_credential_store):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / "storage"))
    monkeypatch.delenv("NLM_AUTH_STORAGE", raising=False)
    reset_config()
    AuthManager("default").save_profile(cookies={"SID": "d"}, email="d@example.com")
    AuthManager("personal").save_profile(cookies={"SID": "p"}, email="p@example.com")
    yield
    reset_config()


def test_profile_modes_lists_every_real_profile_sorted():
    assert protection_flow.profile_modes() == {"default": "file", "personal": "file"}


def test_marker_only_ghost_folder_is_not_listed():
    set_auth_storage_mode("ghost", "protected")  # folder + marker, no credentials
    assert get_profile_dir("ghost", create=False).exists()
    assert "ghost" not in protection_flow.profile_modes()


def test_apply_mode_switches_and_reports_results():
    results, errors = protection_flow.apply_mode("protected", ["personal"])
    assert errors == []
    assert results[0]["profile"] == "personal"
    assert protection_flow.profile_modes() == {"default": "file", "personal": "protected"}


def test_apply_mode_collects_one_error_per_profile(monkeypatch):
    def boom(mode, profile_name=None):
        raise ServiceError("keystore locked")

    monkeypatch.setattr("notebooklm_tools.services.auth_storage.set_storage_mode", boom)
    results, errors = protection_flow.apply_mode("protected", ["default", "personal"])
    assert results == []
    assert errors == ["default: keystore locked", "personal: keystore locked"]


def test_apply_mode_single_target_error_has_no_name_prefix(monkeypatch):
    def boom(mode, profile_name=None):
        raise ServiceError("keystore locked")

    monkeypatch.setattr("notebooklm_tools.services.auth_storage.set_storage_mode", boom)
    _, errors = protection_flow.apply_mode("protected", ["default"])
    assert errors == ["keystore locked"]


def test_pick_returns_empty_list_when_all_already_in_mode(capsys):
    modes = {"default": "protected", "personal": "protected"}
    assert protection_flow.pick_profiles_for_mode(list(modes), "protected", modes) == []
    assert "already protected" in capsys.readouterr().out
