"""Tests for per-profile storage mode selection, validation, and safe config handling."""

import json
import sys

import pytest

from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.utils.config import (
    get_auth_storage_mode,
    get_config,
    get_config_file,
    get_profile_dir,
    reset_config,
    save_config,
    set_auth_storage_mode,
    validate_profile_name,
)


def test_default_storage_mode_is_file():
    """Default mode is file for fresh and existing profiles without a marker."""
    assert get_auth_storage_mode("default") == "file"
    assert get_auth_storage_mode("custom_profile") == "file"


def test_upgraded_install_legacy_files_no_marker_behaves_as_file(tmp_path):
    """An upgraded install with legacy auth.json and no marker defaults to file and does not touch OS store."""
    profile_dir = get_profile_dir("default")
    (profile_dir / "auth.json").write_text(json.dumps({"cookies": {"SID": "123"}}))

    assert get_auth_storage_mode("default") == "file"
    # Verify no marker was created simply by querying mode
    assert not (profile_dir / "storage-mode.json").exists()


def test_two_profiles_with_different_modes():
    """Two profiles can have independent storage modes."""
    set_auth_storage_mode("prof_file", "file")
    set_auth_storage_mode("prof_prot", "protected")

    assert get_auth_storage_mode("prof_file") == "file"
    assert get_auth_storage_mode("prof_prot") == "protected"


def test_env_storage_mode_override(monkeypatch):
    """NLM_AUTH_STORAGE overrides persisted marker for the current process."""
    set_auth_storage_mode("prof1", "file")
    assert get_auth_storage_mode("prof1") == "file"

    monkeypatch.setenv("NLM_AUTH_STORAGE", "protected")
    assert get_auth_storage_mode("prof1") == "protected"

    monkeypatch.setenv("NLM_AUTH_STORAGE", "file")
    assert get_auth_storage_mode("prof1") == "file"


def test_invalid_env_storage_mode_fails_closed(monkeypatch):
    """Invalid NLM_AUTH_STORAGE values fail closed."""
    monkeypatch.setenv("NLM_AUTH_STORAGE", "invalid_mode")
    with pytest.raises(ValueError, match="Invalid NLM_AUTH_STORAGE"):
        get_auth_storage_mode("default")


def test_corrupt_storage_mode_marker_fails_closed():
    """Corrupt storage-mode.json fails closed."""
    marker_path = get_profile_dir("corrupt_prof") / "storage-mode.json"
    marker_path.write_text("{not valid json")

    with pytest.raises(ValueError, match="Corrupt storage-mode.json"):
        get_auth_storage_mode("corrupt_prof")

    # Missing version fails closed
    marker_path.write_text(json.dumps({"mode": "file"}))
    with pytest.raises(ValueError, match="Corrupt storage-mode.json"):
        get_auth_storage_mode("corrupt_prof")

    # Invalid mode in marker fails closed
    marker_path.write_text(json.dumps({"version": 1, "mode": "unknown"}))
    with pytest.raises(ValueError, match="Corrupt storage-mode.json"):
        get_auth_storage_mode("corrupt_prof")


def test_setting_mode_does_not_imply_profile_exists():
    """Setting storage mode on an empty profile must not make profile_exists() true."""
    auth = AuthManager("brand_new_profile")
    assert not auth.profile_exists()

    set_auth_storage_mode("brand_new_profile", "file")
    assert not auth.profile_exists()


def test_profile_name_validation():
    """Profile names must reject traversal, separators, reserved names, and case collisions."""
    # Valid names
    for valid in ("default", "work-account", "personal_2026", "team123"):
        validate_profile_name(valid)

    # Empty
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_profile_name("")

    # Traversal & separators
    for bad in ("..", "../foo", "foo/bar", "foo\\bar", "foo/"):
        with pytest.raises(ValueError, match="path traversal or separators"):
            validate_profile_name(bad)

    # Reserved Windows names
    for reserved in ("CON", "PRN", "AUX", "NUL", "COM1", "LPT1"):
        with pytest.raises(ValueError, match="reserved name"):
            validate_profile_name(reserved)
            validate_profile_name(reserved.lower())

    # Case-insensitive collision detection
    get_profile_dir("myprofile")
    with pytest.raises(ValueError, match="Case-insensitive collision"):
        validate_profile_name("MyProfile")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions check")
def test_marker_file_permissions():
    """storage-mode.json must be written with restrictive 0600 permissions on POSIX."""
    set_auth_storage_mode("perm_test", "file")
    marker = get_profile_dir("perm_test") / "storage-mode.json"
    assert marker.exists()
    assert (marker.stat().st_mode & 0o777) == 0o600


def test_corrupt_config_toml_fails_closed():
    """Corrupt config.toml fails closed with a clean ConfigError."""
    import notebooklm_tools.utils.config as cfg

    config_file = cfg.get_config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("[output\nformat = table (broken toml")

    try:
        cfg.reset_config()
        with pytest.raises(cfg.ConfigError) as exc_info:
            cfg.load_config()

        err = str(exc_info.value)
        assert "Corrupt configuration file" in err
        assert str(config_file) in err
        assert "nlm config reset" in err
    finally:
        config_file.unlink(missing_ok=True)
        cfg.reset_config()


def test_save_config_preserves_unknown_tables_and_no_env_overlay_persistence(monkeypatch):
    """save_config must preserve unknown TOML tables and not persist env overlays."""
    config_file = get_config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        '[output]\nformat = "table"\n\n[custom_plugin]\nenabled = true\nkey = "secret_123"\n'
    )

    # Set an env overlay
    monkeypatch.setenv("NLM_PROFILE", "temporary_env_profile")
    reset_config()
    loaded = get_config()
    assert loaded.auth.default_profile == "temporary_env_profile"

    # Save an unrelated config update
    loaded.output.format = "json"
    save_config(loaded)

    # Inspect the saved raw file
    saved_text = config_file.read_text()
    assert "[custom_plugin]" in saved_text
    assert 'key = "secret_123"' in saved_text
    assert 'format = "json"' in saved_text
    # Environment overlay must NOT be persisted into config.toml!
    assert "temporary_env_profile" not in saved_text


def test_profile_rename_cli_moves_marker_and_updates_default_profile():
    """nlm login profile rename moves storage-mode.json and updates default_profile if matching."""
    from typer.testing import CliRunner

    from notebooklm_tools.cli.main import app

    runner = CliRunner()

    # Create old profile with credentials and marker
    old_auth = AuthManager("old_name")
    old_auth.save_profile(cookies={"test": "cookie"})
    set_auth_storage_mode("old_name", "file")
    assert get_auth_storage_mode("old_name") == "file"

    # Set as default profile
    config = get_config()
    config.auth.default_profile = "old_name"
    save_config(config)

    # Perform CLI rename
    result = runner.invoke(app, ["login", "profile", "rename", "old_name", "new_name"])
    assert result.exit_code == 0
    assert "Renamed profile from 'old_name' to 'new_name'" in result.output

    assert not (get_profile_dir("old_name") / "storage-mode.json").exists()
    assert (get_profile_dir("new_name") / "storage-mode.json").exists()
    assert get_auth_storage_mode("new_name") == "file"

    # default_profile in config should be updated
    reset_config()
    assert get_config().auth.default_profile == "new_name"

    # Restore default
    config = get_config()
    config.auth.default_profile = "default"
    save_config(config)
    reset_config()


def test_profile_rename_cli_refuses_when_credentials_enc_exists():
    """nlm login profile rename refuses when credentials.enc exists."""
    from typer.testing import CliRunner

    from notebooklm_tools.cli.main import app

    runner = CliRunner()

    prof_dir = get_profile_dir("protected_prof")
    prof_dir.mkdir(parents=True, exist_ok=True)
    (prof_dir / "credentials.enc").write_bytes(b"dummy")

    result = runner.invoke(app, ["login", "profile", "rename", "protected_prof", "target_prof"])
    assert result.exit_code != 0
    assert "Renaming protected profiles is coming in a later update" in result.output

    # Original remains untouched
    assert (prof_dir / "credentials.enc").exists()
    assert not (prof_dir.parent / "target_prof").exists()


def test_profile_delete_removes_marker():
    """Deleting a profile removes its storage-mode.json."""
    set_auth_storage_mode("to_delete", "file")
    assert (get_profile_dir("to_delete") / "storage-mode.json").exists()

    auth = AuthManager("to_delete")
    auth.delete_profile()

    assert not (get_profile_dir("to_delete") / "storage-mode.json").exists()
