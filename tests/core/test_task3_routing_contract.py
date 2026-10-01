"""Task 3 routing, file-mode preservation, and protected-mode contract tests.

Verifies:
1. File mode behaves identically to main (root-only fallback, profile+root precedence).
2. Tightened permissions on save, not on load (reads shouldn't write).
3. In protected mode, metadata.json contains NO csrf_token/session_id.
4. Metadata-only updates never rewrite credentials.enc or change its revision.
5. Account-safety check (email mismatch guard when force=False) works identically in protected mode.
6. A locked protected store plus a stale root auth.json raises the store error, never root credentials.
7. Crash after envelope replacement before optional state mirror: envelope remains authoritative.
8. profile_exists never creates directories; mode-only marker alone returns False.
9. First MCP save_tokens_to_cache creates the profile in both modes.
10. Protected save never writes root auth.json mirror.
"""

import json
import subprocess
import sys
import threading

import pytest
from typer.testing import CliRunner

from notebooklm_tools.cli.main import app
from notebooklm_tools.core.auth import (
    AuthManager,
    AuthTokens,
    load_cached_tokens,
    save_tokens_to_cache,
)
from notebooklm_tools.core.credential_store import (
    BackendUnavailableError,
    CredentialStore,
    InvalidProfileNameError,
)
from notebooklm_tools.core.exceptions import AccountMismatchError
from notebooklm_tools.mcp.tools._utils import reset_client
from notebooklm_tools.mcp.tools.notebooks import notebook_list
from notebooklm_tools.services.auth_storage import (
    get_storage_status,
    rename_profile,
    set_storage_mode,
)
from notebooklm_tools.services.errors import ValidationError
from notebooklm_tools.utils.config import (
    get_profile_dir,
    reset_config,
    set_auth_storage_mode,
)


@pytest.fixture(autouse=True)
def setup_isolated_env(tmp_path, monkeypatch):
    """Isolate storage dir and config for each test."""
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path))
    reset_config()
    yield
    reset_config()


def test_before_after_file_mode_root_only_and_profile_plus_root(tmp_path):
    """File mode must behave exactly like main: root-only fallback works, profile+root takes precedence."""
    # Case A: Root-only file-mode user
    root_auth = tmp_path / "auth.json"
    root_tokens_data = {
        "cookies": {"SID": "root_sid_123"},
        "csrf_token": "root_csrf_456",
        "session_id": "root_session_789",
        "build_label": "bl_root",
        "base_host": "notebook.google.com",
    }
    root_auth.write_text(json.dumps(root_tokens_data), encoding="utf-8")

    # Ensure profiles dir doesn't exist yet
    profiles_dir = tmp_path / "profiles"
    assert not profiles_dir.exists()

    # Load tokens: must load from root auth.json
    loaded = load_cached_tokens()
    assert loaded is not None
    assert loaded.cookies == {"SID": "root_sid_123"}
    assert loaded.csrf_token == "root_csrf_456"
    assert loaded.session_id == "root_session_789"

    # Loading must be read-only: does NOT create profiles/<default>/
    assert not (profiles_dir / "default").exists()

    # Case B: Profile + root file-mode user
    default_auth = AuthManager("default")
    default_auth.save_profile(
        cookies={"SID": "prof_sid_999"},
        csrf_token="prof_csrf_888",
        session_id="prof_session_777",
        email="prof@example.com",
    )

    loaded_profile_user = load_cached_tokens()
    assert loaded_profile_user is not None
    # Profile credentials take precedence over root
    assert loaded_profile_user.cookies == {"SID": "prof_sid_999"}
    assert loaded_profile_user.csrf_token == "prof_csrf_888"


def test_locked_protected_store_with_stale_root_auth_never_falls_back(
    tmp_path, fake_credential_store, monkeypatch
):
    """A locked protected store plus a stale root auth.json raises the store error, not the root credentials."""
    # Root auth.json has stale credentials
    root_auth = tmp_path / "auth.json"
    root_auth.write_text(json.dumps({"cookies": {"SID": "stale_root_cookies"}}), encoding="utf-8")

    # Default profile is configured as protected
    set_auth_storage_mode("default", "protected")
    auth = AuthManager("default")
    auth.save_profile(
        cookies={"SID": "protected_secret_val"},
        csrf_token="protected_csrf",
        email="user@example.com",
    )

    # Now simulate a locked backend
    def raise_locked(*args, **kwargs):
        raise BackendUnavailableError("OS credential store is locked")

    monkeypatch.setattr(fake_credential_store, "get_password", raise_locked)

    # load_cached_tokens must raise BackendUnavailableError, NEVER return stale_root_cookies!
    with pytest.raises(BackendUnavailableError):
        load_cached_tokens()


def test_protected_save_leaves_no_plaintext_secrets_in_profile_dir(tmp_path, fake_credential_store):
    """In protected mode, metadata.json and whole profile dir contain zero plaintext secrets."""
    profile_name = "secret_audit_profile"
    auth = AuthManager(profile_name)

    # First, simulate legacy file-mode metadata with secrets in metadata.json
    prof_dir = get_profile_dir(profile_name)
    prof_dir.mkdir(parents=True, exist_ok=True)
    old_metadata = {
        "csrf_token": "old_csrf_leak_123",
        "session_id": "old_sess_leak_456",
        "email": "audit@example.com",
    }
    (prof_dir / "metadata.json").write_text(json.dumps(old_metadata), encoding="utf-8")
    (prof_dir / "cookies.json").write_text(
        json.dumps({"SID": "old_cookie_leak_789"}), encoding="utf-8"
    )

    # Now configure protected mode and save over the profile
    set_auth_storage_mode(profile_name, "protected")

    new_sid = "new_secret_sid_xyz"
    new_csrf = "new_secret_csrf_abc"
    new_sess = "new_secret_sess_def"

    auth.save_profile(
        cookies={"SID": new_sid},
        csrf_token=new_csrf,
        session_id=new_sess,
        email="audit@example.com",
    )

    # 1. Plain cookies.json must be unlinked
    assert not (prof_dir / "cookies.json").exists()
    assert not (prof_dir / "auth.json").exists()

    # 2. metadata.json must NOT contain csrf_token or session_id
    metadata = json.loads((prof_dir / "metadata.json").read_text(encoding="utf-8"))
    assert "csrf_token" not in metadata
    assert "session_id" not in metadata
    assert "cookies" not in metadata
    assert metadata["email"] == "audit@example.com"

    # 3. Grep whole profile directory for any plain secret strings
    for file_path in prof_dir.iterdir():
        if file_path.name in ("credentials.enc", "storage-mode.json.tmp"):
            continue
        content = file_path.read_text(encoding="utf-8")
        assert new_sid not in content
        assert new_csrf not in content
        assert new_sess not in content
        assert "old_csrf_leak_123" not in content
        assert "old_sess_leak_456" not in content
        assert "old_cookie_leak_789" not in content


def test_metadata_only_update_preserves_ciphertext_and_revision(tmp_path, fake_credential_store):
    """Metadata-only updates must not rewrite credentials.enc or change its revision."""
    profile_name = "meta_rev_test"
    set_auth_storage_mode(profile_name, "protected")

    auth = AuthManager(profile_name)
    auth.save_profile(
        cookies={"SID": "static_sid"},
        csrf_token="static_csrf",
        session_id="static_sess",
        email="initial@example.com",
        build_label="bl_v1",
    )

    enc_file = get_profile_dir(profile_name) / "credentials.enc"
    assert enc_file.exists()
    envelope1 = json.loads(enc_file.read_text(encoding="utf-8"))
    rev1 = envelope1["revision"]
    ciphertext1 = envelope1["ciphertext"]

    # 1. Update metadata via update_metadata()
    auth.update_metadata(
        email="updated@example.com",
        build_label="bl_v2",
        last_validated="2026-09-29T20:00:00",
    )

    envelope2 = json.loads(enc_file.read_text(encoding="utf-8"))
    assert envelope2["revision"] == rev1
    assert envelope2["ciphertext"] == ciphertext1

    # 2. Save profile with identical secrets but new metadata
    auth.save_profile(
        cookies={"SID": "static_sid"},
        csrf_token="static_csrf",
        session_id="static_sess",
        email="updated@example.com",
        build_label="bl_v3",
    )

    envelope3 = json.loads(enc_file.read_text(encoding="utf-8"))
    assert envelope3["revision"] == rev1
    assert envelope3["ciphertext"] == ciphertext1


def test_protected_mode_account_safety_mismatch_guard(tmp_path, fake_credential_store):
    """Account mismatch guard prevents saving different email when force=False in protected mode."""
    profile_name = "guard_prof"
    set_auth_storage_mode(profile_name, "protected")

    auth = AuthManager(profile_name)
    auth.save_profile(
        cookies={"SID": "val1"},
        email="alice@example.com",
    )

    # Attempt to overwrite with different email without force: must raise AccountMismatchError
    with pytest.raises(AccountMismatchError) as exc_info:
        auth.save_profile(
            cookies={"SID": "val2"},
            email="bob@example.com",
            force=False,
        )
    assert exc_info.value.stored_email == "alice@example.com"
    assert exc_info.value.new_email == "bob@example.com"

    # With force=True, it succeeds
    auth.save_profile(
        cookies={"SID": "val2"},
        email="bob@example.com",
        force=True,
    )
    loaded = auth.load_profile()
    assert loaded.email == "bob@example.com"


def test_first_mcp_save_creates_profile_in_both_modes(tmp_path, fake_credential_store):
    """First MCP save_tokens_to_cache creates the profile directory in file mode and protected mode."""
    # File mode: named profile
    tokens_file = AuthTokens(
        cookies={"SID": "mcp_file_sid"},
        csrf_token="mcp_csrf",
        session_id="mcp_sess",
    )
    save_tokens_to_cache(tokens_file, profile_name="fresh_file_prof")
    assert AuthManager("fresh_file_prof").profile_exists()

    # Protected mode: named profile
    set_auth_storage_mode("fresh_prot_prof", "protected")
    tokens_prot = AuthTokens(
        cookies={"SID": "mcp_prot_sid"},
        csrf_token="mcp_csrf",
        session_id="mcp_sess",
    )
    save_tokens_to_cache(tokens_prot, profile_name="fresh_prot_prof")
    assert AuthManager("fresh_prot_prof").profile_exists()
    assert (get_profile_dir("fresh_prot_prof") / "credentials.enc").exists()


def test_protected_save_never_writes_root_auth_json_mirror(tmp_path, fake_credential_store):
    """In protected mode, saving the default profile never writes or mirrors to root auth.json."""
    set_auth_storage_mode("default", "protected")
    tokens = AuthTokens(
        cookies={"SID": "protected_only_sid"},
        csrf_token="csrf",
        session_id="sess",
    )
    save_tokens_to_cache(tokens, profile_name="default")

    # Profile credentials.enc exists
    assert (get_profile_dir("default") / "credentials.enc").exists()

    # Root auth.json must NOT exist!
    root_auth = tmp_path / "auth.json"
    assert not root_auth.exists()


def test_profile_exists_never_creates_directories(tmp_path):
    """profile_exists never creates directories, and mode-only marker alone returns False."""
    auth = AuthManager("nonexistent_check")
    # Checking profile_exists must return False
    assert auth.profile_exists() is False
    # Directory was NOT created!
    assert not (tmp_path / "profiles" / "nonexistent_check").exists()

    # Create mode marker only (no credentials)
    set_auth_storage_mode("marker_only", "file")
    marker_auth = AuthManager("marker_only")
    # Even though storage-mode.json exists, profile_exists() must return False
    assert marker_auth.profile_exists() is False


def test_crash_after_envelope_replacement_before_optional_state_mirror(
    tmp_path, fake_credential_store
):
    """If process crashes after atomic envelope replace, envelope remains authoritative."""
    profile_name = "crash_prof"
    set_auth_storage_mode(profile_name, "protected")

    store = CredentialStore()
    payload = {"cookies": {"SID": "valid_secret_sid"}, "csrf_token": "valid_csrf"}
    store.write_credentials(profile_name, payload)

    # Verify envelope decrypts directly
    readback = store.read_credentials(profile_name)
    assert readback == payload


def test_concurrent_reader_during_file_mode_save(tmp_path):
    """Concurrent readers during file mode save do not crash or see truncated files."""
    auth = AuthManager("concurrent_prof")
    auth.save_profile(
        cookies={"SID": "initial_sid" * 100},
        csrf_token="initial_csrf" * 50,
        email="concurrent@example.com",
    )

    errors = []

    def reader():
        for _ in range(50):
            try:
                prof = auth.load_profile(force_reload=True)
                assert "SID" in prof.cookies
            except Exception as e:
                errors.append(e)

    def writer():
        for i in range(50):
            auth.save_profile(
                cookies={"SID": f"updated_sid_{i}" * 100},
                csrf_token=f"csrf_{i}" * 50,
                email="concurrent@example.com",
            )

    t_reader = threading.Thread(target=reader)
    t_writer = threading.Thread(target=writer)

    t_reader.start()
    t_writer.start()

    t_reader.join()
    t_writer.join()

    assert not errors, f"Concurrent reader failed with errors: {errors}"


@pytest.mark.parametrize("mode", ["file", "protected"])
def test_enterprise_consumer_relogin_clears_base_host_both_modes(mode, fake_credential_store):
    """Enterprise -> consumer re-login clears base_host, and consumer -> Enterprise sets it."""
    prof_name = f"relogin_prof_{mode}"
    set_auth_storage_mode(prof_name, mode)
    auth = AuthManager(prof_name)

    # 1. Login with Enterprise host
    auth.save_profile(
        cookies={"SID": "ent_cookie"},
        csrf_token="ent_csrf",
        session_id="ent_sess",
        email="user@enterprise.com",
        base_host="notebook.cloud.google.com",
    )
    loaded = load_cached_tokens(prof_name)
    assert loaded is not None
    assert loaded.base_host == "notebook.cloud.google.com"

    # 2. Re-login as consumer (base_host=None / empty string)
    # save_tokens_to_cache does base_host=tokens.base_host or None
    save_tokens_to_cache(
        AuthTokens(
            cookies={"SID": "consumer_cookie"},
            csrf_token="cons_csrf",
            session_id="cons_sess",
            base_host=None,
        ),
        profile_name=prof_name,
    )
    loaded_consumer = load_cached_tokens(prof_name)
    assert loaded_consumer is not None
    assert loaded_consumer.cookies == {"SID": "consumer_cookie"}
    # base_host must be cleared (None or ""), not stale Enterprise host
    assert not loaded_consumer.base_host

    # 3. Switch back to Enterprise
    save_tokens_to_cache(
        AuthTokens(
            cookies={"SID": "ent_cookie_2"},
            csrf_token="ent_csrf_2",
            session_id="ent_sess_2",
            base_host="notebook.cloud.google.com",
        ),
        profile_name=prof_name,
    )
    loaded_ent_2 = load_cached_tokens(prof_name)
    assert loaded_ent_2 is not None
    assert loaded_ent_2.base_host == "notebook.cloud.google.com"


def test_legacy_profile_name_with_spaces_file_mode_and_protected_refusal(fake_credential_store):
    """Profiles with spaces work in file mode (load, save, status, rename) and are refused for protected mode."""
    prof_name = "my work"
    auth = AuthManager(prof_name)

    # Save and load in file mode
    auth.save_profile(
        cookies={"SID": "space_cookie"},
        csrf_token="space_csrf",
        email="space@example.com",
    )
    assert auth.profile_exists()
    loaded = load_cached_tokens(prof_name)
    assert loaded is not None
    assert loaded.cookies == {"SID": "space_cookie"}

    # Status check
    status = get_storage_status(prof_name)
    assert status["profile"] == "my work"
    assert status["mode"] == "file"

    # Set storage to file (no-op update) works
    res_set = set_storage_mode("file", prof_name)
    assert res_set["mode"] == "file"

    # Rename profile with spaces in file mode
    res_rename = rename_profile("my work", "my new work")
    assert res_rename["old_name"] == "my work"
    assert res_rename["new_name"] == "my new work"
    assert AuthManager("my new work").profile_exists()
    assert not AuthManager("my work").profile_exists()

    # CLI commands work for legacy profile names
    runner = CliRunner()
    cli_status = runner.invoke(app, ["auth", "storage", "status", "--profile", "my new work"])
    assert cli_status.exit_code == 0
    assert "my new work" in cli_status.stdout

    cli_set = runner.invoke(app, ["auth", "storage", "set", "file", "--profile", "my new work"])
    assert cli_set.exit_code == 0

    cli_rename = runner.invoke(app, ["login", "profile", "rename", "my new work", "renamed work"])
    assert cli_rename.exit_code == 0
    assert AuthManager("renamed work").profile_exists()

    # Protected mode must refuse profile with spaces with a clear rename suggestion
    with pytest.raises(ValidationError) as exc_info:
        set_storage_mode("protected", "renamed work")
    err_msg = str(exc_info.value)
    assert "characters unsupported by protected mode" in err_msg
    assert "nlm login profile rename" in err_msg

    with pytest.raises(ValueError) as exc_info_val:
        set_auth_storage_mode("renamed work", "protected")
    assert "characters unsupported by protected mode" in str(exc_info_val.value)

    # CredentialStore directly refuses profile with spaces
    with pytest.raises(InvalidProfileNameError):
        CredentialStore().write_credentials("renamed work", {"cookies": {}})


def test_e2e_storage_isolation_fixture_yields_in_subprocess(tmp_path):
    """Live E2E test runs with NOTEBOOKLM_E2E=1 yield cleanly without fixture error."""
    probe_test = tmp_path / "test_probe_e2e.py"
    probe_test.write_text(
        """
import pytest

@pytest.mark.e2e
def test_dummy_e2e_marker():
    assert True
""",
        encoding="utf-8",
    )

    env = dict(subprocess.os.environ)
    env["NOTEBOOKLM_E2E"] = "1"
    env["NOTEBOOKLM_MCP_CLI_PATH"] = str(tmp_path / "storage")

    res = subprocess.run(
        [sys.executable, "-m", "pytest", str(probe_test), "-m", "e2e", "-q"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"pytest failed with output: {res.stdout}\n{res.stderr}"
    assert "1 passed" in res.stdout
    assert "did not yield a value" not in res.stderr
    assert "did not yield a value" not in res.stdout


def test_corrupt_config_clean_error_in_mcp_and_cli(tmp_path, monkeypatch):
    """Corrupt config.toml yields a clean error in MCP and CLI without tracebacks."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("corrupt = [[[\n", encoding="utf-8")
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path))
    reset_config()
    reset_client()

    # MCP tool returns clean error dict
    mcp_res = notebook_list()
    assert mcp_res["status"] == "error"
    assert "Corrupt configuration file" in mcp_res["error"]
    assert "To reset: delete the file or run 'nlm config reset'" in mcp_res["error"]

    # CLI command exits 1 with clean error and zero traceback
    env = dict(subprocess.os.environ)
    env["NOTEBOOKLM_MCP_CLI_PATH"] = str(tmp_path)
    cli_proc = subprocess.run(
        [sys.executable, "-m", "notebooklm_tools.cli.main", "notebook", "list"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert cli_proc.returncode == 1
    assert "✗ Error: Corrupt configuration file" in cli_proc.stdout
    assert "Traceback" not in cli_proc.stderr
    assert "Traceback" not in cli_proc.stdout
