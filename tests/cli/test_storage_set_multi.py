"""nlm auth storage set: picker, --all, 'still plain' notice, and real-shaped backup cleanup."""

import json

import pytest
from typer.testing import CliRunner

from notebooklm_tools.cli import main
from notebooklm_tools.cli.main import app
from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.services.auth_storage import find_plain_backup_files
from notebooklm_tools.utils.config import get_auth_storage_mode, get_profile_dir, reset_config

runner = CliRunner()

# Same shape as a real profiles/<name>/cookies.json (list of cookie objects).
REAL_COOKIE_LIST = [
    {"name": "SID", "value": "x", "domain": ".google.com", "path": "/"},
    {"name": "__Secure-1PSID", "value": "y", "domain": ".google.com", "path": "/"},
]


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch, fake_credential_store):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / "storage"))
    reset_config()
    AuthManager("default").save_profile(cookies={"SID": "d"}, email="d@example.com")
    AuthManager("personal").save_profile(cookies={"SID": "p"}, email="p@example.com")
    yield
    reset_config()


def test_real_shaped_cookie_backup_is_offered_for_cleanup():
    bak = get_profile_dir("default") / "cookies.json.bak"
    bak.write_text(json.dumps(REAL_COOKIE_LIST), encoding="utf-8")
    assert bak in find_plain_backup_files("default")


def test_legacy_auth_json_backup_is_offered_for_cleanup(tmp_path, monkeypatch):
    from pathlib import Path

    from notebooklm_tools.utils.config import get_legacy_storage_dir

    # Legacy files only count when storage sits at its normal home location
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(Path.home() / ".notebooklm-mcp-cli"))
    reset_config()
    AuthManager("default").save_profile(cookies={"SID": "d"}, email="d@example.com")

    legacy = get_legacy_storage_dir()
    legacy.mkdir(parents=True, exist_ok=True)
    old = legacy / "auth.json.backup"
    old.write_text(json.dumps({"cookies": {"SID": "old"}, "csrf_token": "t"}), encoding="utf-8")
    assert old.is_relative_to(tmp_path.parent)  # isolated fake HOME, never the real one
    assert old in find_plain_backup_files("default")


def test_non_login_list_is_not_offered():
    bak = get_profile_dir("default") / "cookies.json.bak"
    bak.write_text(json.dumps(["not", "cookies"]), encoding="utf-8")
    assert bak not in find_plain_backup_files("default")


def test_default_only_run_says_which_profiles_are_still_plain():
    res = runner.invoke(app, ["auth", "storage", "set", "protected"])
    assert res.exit_code == 0, res.output
    assert get_auth_storage_mode("default") == "protected"
    assert get_auth_storage_mode("personal") == "file"
    assert "Still plain: personal" in res.output
    assert "nlm auth storage set protected --all" in res.output


def test_all_flag_protects_every_profile_and_offers_one_cleanup():
    for name in ("default", "personal"):
        (get_profile_dir(name) / "cookies.json.bak").write_text(
            json.dumps(REAL_COOKIE_LIST), encoding="utf-8"
        )
    res = runner.invoke(app, ["auth", "storage", "set", "protected", "--all"], input="y\n")
    assert res.exit_code == 0, res.output
    assert get_auth_storage_mode("default") == "protected"
    assert get_auth_storage_mode("personal") == "protected"
    assert res.output.count("Delete these 2 old plain copies?") == 1
    assert "Removed 2 old plain copies." in res.output
    assert "Still plain" not in res.output


def test_picker_selection_switches_chosen_profiles(monkeypatch):
    monkeypatch.setattr(main, "_is_terminal", lambda: True)
    monkeypatch.setattr(main, "_pick_profiles_for_mode", lambda *a: ["personal"])
    res = runner.invoke(app, ["auth", "storage", "set", "protected"])
    assert res.exit_code == 0, res.output
    assert get_auth_storage_mode("personal") == "protected"
    assert get_auth_storage_mode("default") == "file"
    assert "Still plain: default" in res.output


def test_picker_with_nothing_selected_changes_nothing(monkeypatch):
    monkeypatch.setattr(main, "_is_terminal", lambda: True)
    monkeypatch.setattr(main, "_pick_profiles_for_mode", lambda *a: [])
    res = runner.invoke(app, ["auth", "storage", "set", "protected"])
    assert res.exit_code == 0, res.output
    assert "Nothing selected" in res.output
    assert get_auth_storage_mode("default") == "file"
    assert get_auth_storage_mode("personal") == "file"


def test_picker_not_used_with_explicit_profile(monkeypatch):
    monkeypatch.setattr(main, "_is_terminal", lambda: True)

    def _fail(*a):
        raise AssertionError("picker must not open when --profile is given")

    monkeypatch.setattr(main, "_pick_profiles_for_mode", _fail)
    res = runner.invoke(app, ["auth", "storage", "set", "protected", "--profile", "personal"])
    assert res.exit_code == 0, res.output
    assert get_auth_storage_mode("personal") == "protected"


def test_picker_reports_when_everything_is_already_protected():
    picked = main._pick_profiles_for_mode(
        ["default", "personal"], "protected", {"default": "protected", "personal": "protected"}
    )
    assert picked == []


def test_backups_of_already_protected_profiles_are_offered(monkeypatch):
    """Jacob's case: 'default' protected earlier with a backup left; switching 'personal' offers it."""
    runner.invoke(app, ["auth", "storage", "set", "protected", "--profile", "default"], input="n\n")
    bak = get_profile_dir("default") / "cookies.json.bak"
    bak.write_text(json.dumps(REAL_COOKIE_LIST), encoding="utf-8")

    monkeypatch.setattr(main, "_is_terminal", lambda: True)
    monkeypatch.setattr(main, "_pick_profiles_for_mode", lambda *a: ["personal"])
    res = runner.invoke(app, ["auth", "storage", "set", "protected"], input="y\n")
    assert res.exit_code == 0, res.output
    assert "Delete this old plain copy?" in res.output
    assert not bak.exists()


def test_cleanup_offered_even_when_everything_is_already_protected(monkeypatch):
    runner.invoke(app, ["auth", "storage", "set", "protected", "--all"], input="n\n")
    bak = get_profile_dir("personal") / "cookies.json.bak"
    bak.write_text(json.dumps(REAL_COOKIE_LIST), encoding="utf-8")

    monkeypatch.setattr(main, "_is_terminal", lambda: True)
    res = runner.invoke(app, ["auth", "storage", "set", "protected"], input="n\n")
    assert res.exit_code == 0, res.output
    assert "All saved logins are already protected" in res.output
    assert "Nothing selected" not in res.output
    assert "Delete this old plain copy?" in res.output
    assert bak.exists()


def test_cleanup_question_without_keyboard_keeps_files():
    bak = get_profile_dir("default") / "cookies.json.bak"
    bak.write_text(json.dumps(REAL_COOKIE_LIST), encoding="utf-8")
    res = runner.invoke(
        app, ["auth", "storage", "set", "protected", "--profile", "default"], input=""
    )
    assert res.exit_code == 0, res.output
    assert "Kept them (no answer)" in res.output
    assert bak.exists()
