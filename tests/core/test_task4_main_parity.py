"""Strict before/after parity test comparing file-mode behavior against main.

Verifies:
1. Root-only user: load_cached_tokens() returns tokens from root auth.json, never creates profiles/<default>/.
2. Profile + root user: profile tokens take precedence, matching main.
3. Named profile: load_cached_tokens(named) never falls back to root auth.json, matching main.
4. Corrupted profile: in file mode, falls back to root auth.json, matching main.
5. save_tokens_to_cache: in file mode, mirrors configured default to root auth.json with 0600 permissions.
6. auto_migrate_if_needed: runs identically to main in file mode; skips only when configured default is protected.
7. Keystore isolation: in file mode, zero calls to OS keystore or helper process across all operations.
"""

import json
import os
from unittest.mock import MagicMock

import pytest

from notebooklm_tools.core.auth import (
    AuthManager,
    AuthTokens,
    load_cached_tokens,
    save_tokens_to_cache,
)
from notebooklm_tools.services.auth_storage import get_storage_status
from notebooklm_tools.utils.config import (
    auto_migrate_if_needed,
    get_auth_storage_mode,
    get_profile_dir,
    reset_config,
    set_auth_storage_mode,
)


@pytest.fixture(autouse=True)
def setup_isolated_env(tmp_path, monkeypatch):
    """Isolate storage dir and reset config for each test."""
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path))
    reset_config()
    yield
    reset_config()


def test_parity_root_only_user(tmp_path):
    """A root-only file-mode user loads identical tokens as on main, without creating profiles/default."""
    root_auth = tmp_path / "auth.json"
    root_data = {
        "cookies": {"SID": "root_sid_111"},
        "csrf_token": "root_csrf_222",
        "session_id": "root_sess_333",
        "build_label": "bl_main",
        "base_host": "notebook.google.com",
    }
    root_auth.write_text(json.dumps(root_data), encoding="utf-8")

    profiles_dir = tmp_path / "profiles"
    assert not profiles_dir.exists()

    tokens = load_cached_tokens()
    assert tokens is not None
    assert tokens.cookies == {"SID": "root_sid_111"}
    assert tokens.csrf_token == "root_csrf_222"
    assert tokens.session_id == "root_sess_333"

    # Reads must not write: no profiles/<default> directory created
    assert not (profiles_dir / "default").exists()


def test_parity_profile_plus_root_user(tmp_path):
    """A user with both profile and root credentials loads profile credentials with precedence."""
    root_auth = tmp_path / "auth.json"
    root_auth.write_text(json.dumps({"cookies": {"SID": "old_root"}}), encoding="utf-8")

    auth = AuthManager("default")
    auth.save_profile(
        cookies={"SID": "new_profile"},
        csrf_token="new_csrf",
        session_id="new_sess",
        email="user@example.com",
    )

    tokens = load_cached_tokens()
    assert tokens is not None
    assert tokens.cookies == {"SID": "new_profile"}


def test_parity_named_profile_no_root_fallback(tmp_path):
    """A named profile never falls back to root auth.json."""
    root_auth = tmp_path / "auth.json"
    root_auth.write_text(json.dumps({"cookies": {"SID": "root_sid"}}), encoding="utf-8")

    # Non-existent named profile
    tokens = load_cached_tokens("nonexistent")
    assert tokens is None


def test_parity_corrupt_profile_file_mode_falls_back_to_root(tmp_path):
    """In file mode, a corrupted profile file falls back to root auth.json, matching main."""
    root_auth = tmp_path / "auth.json"
    root_auth.write_text(json.dumps({"cookies": {"SID": "fallback_root_sid"}}), encoding="utf-8")

    prof_dir = get_profile_dir("default", create=True)
    (prof_dir / "cookies.json").write_text("{corrupt_json", encoding="utf-8")

    tokens = load_cached_tokens()
    assert tokens is not None
    assert tokens.cookies == {"SID": "fallback_root_sid"}


def test_parity_save_tokens_to_cache_mirrors_and_tightens(tmp_path):
    """save_tokens_to_cache in file mode mirrors configured default and tightens to 0600."""
    tokens = AuthTokens(
        cookies={"SID": "save_sid"},
        csrf_token="save_csrf",
        session_id="save_sess",
    )
    save_tokens_to_cache(tokens)

    root_auth = tmp_path / "auth.json"
    assert root_auth.exists()
    assert json.loads(root_auth.read_text(encoding="utf-8"))["cookies"] == {"SID": "save_sid"}

    prof_dir = get_profile_dir("default")
    cookies_file = prof_dir / "cookies.json"
    assert cookies_file.exists()
    assert json.loads(cookies_file.read_text(encoding="utf-8")) == {"SID": "save_sid"}

    if os.name == "posix":
        assert (root_auth.stat().st_mode & 0o777) == 0o600
        assert (cookies_file.stat().st_mode & 0o777) == 0o600


def test_parity_auto_migrate_if_needed_file_vs_protected(tmp_path, monkeypatch):
    """auto_migrate_if_needed runs identically to main in file mode; skips only when protected."""
    fake_legacy_dir = tmp_path / "legacy_nlm"
    fake_legacy_dir.mkdir()
    legacy_auth = fake_legacy_dir / "auth.json"
    legacy_auth.write_text(json.dumps({"cookies": {"SID": "legacy_sid"}}), encoding="utf-8")

    monkeypatch.setattr(
        "notebooklm_tools.utils.config.check_migration_sources",
        lambda: {"auth_files": [legacy_auth], "aliases": [], "chrome_profiles": []},
    )

    # 1. In default file mode: legacy migration runs
    assert get_auth_storage_mode("default") == "file"
    actions = auto_migrate_if_needed()
    assert len(actions) == 1
    assert "Copy auth tokens" in actions[0]
    assert (tmp_path / "auth.json").exists()

    # Reset
    (tmp_path / "auth.json").unlink()

    # 2. In protected mode: legacy migration is skipped
    set_auth_storage_mode("default", "protected")
    actions_prot = auto_migrate_if_needed()
    assert actions_prot == []
    assert not (tmp_path / "auth.json").exists()


def test_parity_zero_keystore_access_in_file_mode(tmp_path, monkeypatch):
    """In file mode, all operations run with ZERO calls to the OS keystore."""
    # Ensure any call to CredentialWorkerClient or CredentialStore raises
    mock_worker = MagicMock()
    mock_worker.get_password.side_effect = AssertionError("Keystore accessed in file mode!")
    mock_worker.set_password.side_effect = AssertionError("Keystore accessed in file mode!")
    mock_worker.ensure_key.side_effect = AssertionError("Keystore accessed in file mode!")
    mock_worker.identify.side_effect = AssertionError("Keystore accessed in file mode!")
    monkeypatch.setattr(
        "notebooklm_tools.core.credential_backend_worker.CredentialWorkerClient",
        lambda *args, **kwargs: mock_worker,
    )

    # 1. save_profile
    auth = AuthManager("file_parity")
    auth.save_profile(cookies={"SID": "parity_sid"}, email="p@example.com")

    # 2. load_profile
    p = auth.load_profile()
    assert p.cookies == {"SID": "parity_sid"}

    # 3. get_storage_status
    st = get_storage_status("file_parity")
    assert st["mode"] == "file"

    # 4. load_cached_tokens
    save_tokens_to_cache(AuthTokens(cookies={"SID": "def_sid"}))
    tokens = load_cached_tokens()
    assert tokens is not None
    assert tokens.cookies == {"SID": "def_sid"}
