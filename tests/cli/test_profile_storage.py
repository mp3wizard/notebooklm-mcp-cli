"""Tests for profile rename orchestration, layering, and storage mode preservation."""

import json

import pytest
from typer.testing import CliRunner

from notebooklm_tools.cli.main import app
from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.services.auth_storage import rename_profile
from notebooklm_tools.services.errors import (
    ConflictError,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from notebooklm_tools.utils.config import (
    get_auth_storage_mode,
    get_config,
    get_profile_dir,
    get_profiles_dir,
    get_storage_dir,
    save_config,
    set_auth_storage_mode,
)

runner = CliRunner()


def test_rename_profile_moves_file_mode_profile(fake_credential_store):
    """rename_profile moves files, preserves explicit file mode marker, and updates default."""
    # Setup source profile with explicit file mode marker and credentials
    set_auth_storage_mode("source_prof", "file")
    auth = AuthManager("source_prof")
    auth.save_profile(
        cookies={"SID": "session_val"},
        csrf_token="csrf_val",
        session_id="sess_val",
        email="user@example.com",
    )
    config = get_config()
    config.auth.default_profile = "source_prof"
    save_config(config)

    # Perform rename via service
    res = rename_profile("source_prof", "dest_prof")
    assert res["old_name"] == "source_prof"
    assert res["new_name"] == "dest_prof"
    assert res["is_default"] is True

    # Source must no longer exist
    assert not AuthManager("source_prof").profile_exists()
    assert not (get_profiles_dir() / "source_prof").exists()

    # Destination exists and has identical credentials
    dest_auth = AuthManager("dest_prof")
    assert dest_auth.profile_exists()
    loaded = dest_auth.load_profile()
    assert loaded.cookies == {"SID": "session_val"}
    assert loaded.csrf_token == "csrf_val"
    assert loaded.email == "user@example.com"

    # Preserved raw marker without relying on env var
    marker_path = get_profile_dir("dest_prof") / "storage-mode.json"
    assert marker_path.exists()
    marker_data = json.loads(marker_path.read_text(encoding="utf-8"))
    assert marker_data["mode"] == "file"

    # Default profile was updated
    assert get_config().auth.default_profile == "dest_prof"


def test_rename_profile_moves_saved_browser_identity(fake_credential_store):
    """The saved browser user-data-dir follows the auth profile name."""
    AuthManager("browser_old").save_profile(cookies={"SID": "cookie"})

    chrome_root = get_storage_dir() / "chrome-profiles"
    old_browser = chrome_root / "browser_old"
    new_browser = chrome_root / "browser_new"
    old_browser.mkdir(parents=True)
    (old_browser / "identity.txt").write_text("owned", encoding="utf-8")

    rename_profile("browser_old", "browser_new")

    assert not old_browser.exists()
    assert (new_browser / "identity.txt").read_text(encoding="utf-8") == "owned"
    assert AuthManager("browser_new").profile_exists()


def test_rename_profile_refuses_browser_identity_collision(fake_credential_store):
    """Never rename auth while an unrelated browser identity owns the target name."""
    AuthManager("browser_src").save_profile(cookies={"SID": "cookie"})

    chrome_root = get_storage_dir() / "chrome-profiles"
    (chrome_root / "browser_src").mkdir(parents=True)
    (chrome_root / "browser_dest").mkdir(parents=True)

    with pytest.raises(ConflictError, match="Browser profile 'browser_dest' already exists"):
        rename_profile("browser_src", "browser_dest")

    assert AuthManager("browser_src").profile_exists()
    assert not AuthManager("browser_dest").profile_exists()


def test_rename_profile_rolls_back_browser_and_auth_on_config_failure(
    fake_credential_store,
    monkeypatch,
):
    """A late config failure restores both auth and browser identity."""
    AuthManager("rollback_old").save_profile(cookies={"SID": "cookie"})
    config = get_config()
    config.auth.default_profile = "rollback_old"
    save_config(config)

    chrome_root = get_storage_dir() / "chrome-profiles"
    old_browser = chrome_root / "rollback_old"
    new_browser = chrome_root / "rollback_new"
    old_browser.mkdir(parents=True)
    (old_browser / "identity.txt").write_text("owned", encoding="utf-8")

    def fail_save(_config):
        raise OSError("simulated config write failure")

    monkeypatch.setattr(
        "notebooklm_tools.utils.config.save_config",
        fail_save,
    )

    with pytest.raises(OSError, match="simulated config write failure"):
        rename_profile("rollback_old", "rollback_new")

    assert AuthManager("rollback_old").profile_exists()
    assert not AuthManager("rollback_new").profile_exists()
    assert (old_browser / "identity.txt").read_text(encoding="utf-8") == "owned"
    assert not new_browser.exists()
    assert get_config().auth.default_profile == "rollback_old"


def test_rename_profile_refuses_leftover_browser_dir_at_destination(fake_credential_store):
    """A stray browser dir under the new name must not be adopted by the renamed profile."""
    AuthManager("leftover_src").save_profile(cookies={"SID": "cookie"})

    stray = get_storage_dir() / "chrome-profiles" / "leftover_dest"
    stray.mkdir(parents=True)

    with pytest.raises(ConflictError, match="Browser profile 'leftover_dest' already exists"):
        rename_profile("leftover_src", "leftover_dest")

    assert AuthManager("leftover_src").profile_exists()
    assert not AuthManager("leftover_dest").profile_exists()


def test_rename_profile_moves_firefox_identity_too(fake_credential_store):
    """The saved Firefox profile follows the auth profile name, like the Chrome one."""
    AuthManager("ff_old").save_profile(cookies={"SID": "cookie"})

    firefox_root = get_storage_dir() / "firefox-profiles"
    (firefox_root / "ff_old").mkdir(parents=True)
    (firefox_root / "ff_old" / "identity.txt").write_text("owned", encoding="utf-8")

    rename_profile("ff_old", "ff_new")

    assert not (firefox_root / "ff_old").exists()
    assert (firefox_root / "ff_new" / "identity.txt").read_text(encoding="utf-8") == "owned"


def test_rename_profile_reads_raw_marker_without_nlm_auth_storage_env_bleed(
    fake_credential_store, monkeypatch
):
    """Renaming a profile when NLM_AUTH_STORAGE is set in env must NOT persist the env override."""
    # Source profile has NO storage-mode.json marker on disk (default file mode)
    auth = AuthManager("plain_prof")
    auth.save_profile(
        cookies={"SID": "plain_val"},
        csrf_token="token",
        email="plain@example.com",
    )
    source_dir = get_profiles_dir() / "plain_prof"
    assert not (source_dir / "storage-mode.json").exists()

    # Set NLM_AUTH_STORAGE in environment
    monkeypatch.setenv("NLM_AUTH_STORAGE", "protected")
    # Even though get_auth_storage_mode reports "protected" due to env overlay:
    assert get_auth_storage_mode("plain_prof") == "protected"

    # Rename must inspect disk directly and NOT write a protected marker to dest
    res = rename_profile("plain_prof", "new_plain_prof")
    assert res["new_name"] == "new_plain_prof"

    dest_dir = get_profiles_dir() / "new_plain_prof"
    # No storage-mode.json was created on disk because source had none!
    assert not (dest_dir / "storage-mode.json").exists()


def test_rename_refuses_protected_profile(fake_credential_store):
    """Renaming a protected profile is refused with a clear message."""
    prof_dir = get_profile_dir("prot_prof")
    (prof_dir / "credentials.enc").write_bytes(b"dummy_ciphertext")

    # Service raises ServiceError
    with pytest.raises(ServiceError) as exc_info:
        rename_profile("prot_prof", "new_prot")
    assert "Renaming protected profiles is coming in a later update" in str(exc_info.value)


def test_rename_validates_profile_names_and_collisions():
    """rename_profile enforces name validation and target non-existence."""
    with pytest.raises(ValidationError):
        rename_profile("../invalid", "valid")

    with pytest.raises(NotFoundError):
        rename_profile("nonexistent_profile_xyz", "valid")

    auth = AuthManager("existing_dest")
    auth.save_profile(cookies={"SID": "1"}, email="dest@example.com")
    auth_src = AuthManager("src_prof")
    auth_src.save_profile(cookies={"SID": "2"}, email="src@example.com")

    with pytest.raises(ConflictError):
        rename_profile("src_prof", "existing_dest")


def test_cli_profile_rename_thin_wrapper(fake_credential_store):
    """CLI profile rename calls auth_storage.rename_profile and outputs success."""
    auth = AuthManager("cli_old")
    auth.save_profile(cookies={"SID": "val"}, email="cli@example.com")

    result = runner.invoke(app, ["login", "profile", "rename", "cli_old", "cli_new"])
    assert result.exit_code == 0
    assert "Renamed profile from 'cli_old' to 'cli_new'" in result.stdout
    assert AuthManager("cli_new").profile_exists()
    assert not AuthManager("cli_old").profile_exists()
