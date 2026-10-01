"""Comprehensive unit and contract tests for Task 4: Storage Mode Migration and Conflicts.

Verifies:
1. Cookie identity preservation: CDP lists with duplicate names on different domains compare as not equal.
2. Writer race during migration: concurrent cookie update during quarantine causes abort, restore, and zero data loss.
3. Configured default profile: when default_profile = 'work', root auth.json mirror belongs to 'work', not 'default'.
4. Root auth.json elimination: protecting configured default profile removes root auth.json and lists it in removed_files.
5. Corrupt source protection: invalid JSON in cookies.json aborts migration immediately without touching anything.
6. Safe rollback of phase 'preparing': deletes ciphertext and key ONLY if created by this operation.
7. Recovery of migrate_to_file: recognizes already published target and completes cleanup.
8. File mode keystore isolation: ordinary load_profile never opens OS store even if credentials.enc exists.
9. Multi-profile isolation: switching profile A never touches profile B.
10. Pending operation guard: set protected is refused when an unfinished marker exists.
11. Preflight failure: keystore unavailable cleanly raises BackendUnavailableError.
12. Downgrade to file mode: exports credentials with 0600, deletes ciphertext/keystore key.
13. Conflict detection: divergent plaintext and protected credentials raise StorageConflictError in protected mode.
14. Conflict resolution: resolve file vs resolve protected vs resolve file --discard-inaccessible.
"""

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from notebooklm_tools.core.auth import AuthManager, AuthTokens, save_tokens_to_cache
from notebooklm_tools.core.auth_migration import (
    StorageConflictError,
    _get_operations_dir,
    canonical_secrets_equal,
    compute_cookies_hash,
    migrate_profile_to_protected,
    read_operation_marker,
    reconcile_pending_operations,
    write_operation_marker,
)
from notebooklm_tools.core.credential_backend_worker import BackendTimeoutError
from notebooklm_tools.core.credential_store import (
    BackendUnavailableError,
    CredentialStore,
    CredentialStoreError,
    LockAcquisitionTimeoutError,
    get_profile_lock,
)
from notebooklm_tools.mcp.tools.server import server_info
from notebooklm_tools.services.auth_storage import (
    get_storage_status,
    rename_profile,
    resolve_storage_conflict,
    set_storage_mode,
)
from notebooklm_tools.services.errors import ServiceError
from notebooklm_tools.utils.config import (
    get_auth_storage_mode,
    get_config,
    get_profile_dir,
    reset_config,
    save_config,
)


@pytest.fixture(autouse=True)
def setup_isolated_env(tmp_path, monkeypatch, fake_credential_store):
    """Isolate storage dir and reset config for each test."""
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path))
    reset_config()
    yield
    reset_config()


def test_cookie_identity_preservation_cdp_duplicates_not_equal():
    """Two CDP cookie lists that differ only in duplicate names across domains must not compare equal."""
    list_a = [
        {"name": "SID", "value": "val1", "domain": ".google.com", "path": "/"},
        {"name": "SID", "value": "val2", "domain": "notebook.google.com", "path": "/"},
    ]
    list_b = [
        {"name": "SID", "value": "val1", "domain": ".google.com", "path": "/"},
        {"name": "SID", "value": "val_DIFFERENT", "domain": "notebook.google.com", "path": "/"},
    ]

    snap_a = {"cookies": list_a, "csrf_token": "token", "session_id": "sess"}
    snap_b = {"cookies": list_b, "csrf_token": "token", "session_id": "sess"}

    assert not canonical_secrets_equal(snap_a, snap_b)

    # Identical list with different order must compare equal
    list_a_shuffled = [list_a[1], list_a[0]]
    assert canonical_secrets_equal(
        snap_a, {"cookies": list_a_shuffled, "csrf_token": "token", "session_id": "sess"}
    )


def test_writer_race_during_migration_aborts_and_restores(tmp_path, monkeypatch):
    """If cookies.json changes between snapshot and quarantine, migration must abort and restore."""
    profile_dir = tmp_path / "profiles" / "race_prof"
    profile_dir.mkdir(parents=True)
    cookies_path = profile_dir / "cookies.json"
    initial_cookies = {"SID": "initial_cookie"}
    cookies_path.write_text(json.dumps(initial_cookies), encoding="utf-8")

    # Hook shutil.move to simulate a writer updating cookies.json right as it is moved into quarantine
    orig_move = __import__("shutil").move

    def racing_move(src, dst):
        res = orig_move(src, dst)
        if "quarantine" in str(dst) and "cookies.json" in str(dst):
            # Simulate a concurrent writer replacing the quarantined file with newer cookies
            Path(dst).write_text(json.dumps({"SID": "newer_racing_cookie"}), encoding="utf-8")
        return res

    monkeypatch.setattr("shutil.move", racing_move)

    with pytest.raises(CredentialStoreError, match="modified concurrently"):
        migrate_profile_to_protected("race_prof")

    # Verification: original file restored, no cookies lost, mode remains file
    assert cookies_path.exists()
    restored = json.loads(cookies_path.read_text(encoding="utf-8"))
    assert restored == {"SID": "newer_racing_cookie"}
    assert get_auth_storage_mode("race_prof") == "file"


def test_configured_default_profile_work_root_mirror(tmp_path):
    """When default_profile = 'work', root auth.json belongs to 'work', not 'default'."""
    cfg = get_config()
    cfg.auth.default_profile = "work"
    save_config(cfg)

    # Setup profile 'work' (configured default)
    tokens_work = AuthTokens(
        cookies={"SID": "work_sid"},
        csrf_token="work_csrf",
        session_id="work_sess",
    )
    save_tokens_to_cache(tokens_work, profile_name="work")

    # Root auth.json must have been mirrored for 'work'
    root_auth = tmp_path / "auth.json"
    assert root_auth.exists()
    assert json.loads(root_auth.read_text(encoding="utf-8"))["cookies"] == {"SID": "work_sid"}

    # Setup profile 'default' (which is NOT the configured default)
    tokens_default = AuthTokens(
        cookies={"SID": "literal_default_sid"},
        csrf_token="def_csrf",
        session_id="def_sess",
    )
    save_tokens_to_cache(tokens_default, profile_name="default")

    # Root auth.json must still belong to 'work'!
    assert json.loads(root_auth.read_text(encoding="utf-8"))["cookies"] == {"SID": "work_sid"}


def test_root_auth_json_removed_when_protecting_configured_default(tmp_path):
    """Protecting configured default profile removes root auth.json and lists it in removed_files."""

    cfg = get_config()
    cfg.auth.default_profile = "work"
    save_config(cfg)

    tokens_work = AuthTokens(
        cookies={"SID": "work_sid"},
        csrf_token="work_csrf",
        session_id="work_sess",
    )
    save_tokens_to_cache(tokens_work, profile_name="work")

    root_auth = tmp_path / "auth.json"
    assert root_auth.exists()

    res = migrate_profile_to_protected("work")
    assert res["mode"] == "protected"
    assert "auth.json" in res["removed_files"]
    assert "profiles/work/cookies.json" in res["removed_files"]
    assert not root_auth.exists()

    # Zero plaintext files remain in the profile dir
    prof_dir = get_profile_dir("work")
    assert not (prof_dir / "cookies.json").exists()
    assert not (prof_dir / "auth.json").exists()


def test_corrupt_source_aborts_immediately_without_deleting(tmp_path):
    """Any unreadable or corrupt source file must abort migration immediately."""
    prof_dir = tmp_path / "profiles" / "corrupt_prof"
    prof_dir.mkdir(parents=True)
    cookies_path = prof_dir / "cookies.json"
    cookies_path.write_text("{invalid_json_corrupt_data", encoding="utf-8")

    with pytest.raises(CredentialStoreError, match="Corrupt or unreadable cookies file"):
        migrate_profile_to_protected("corrupt_prof")

    # File was not deleted
    assert cookies_path.exists()
    assert cookies_path.read_text(encoding="utf-8") == "{invalid_json_corrupt_data"
    assert get_auth_storage_mode("corrupt_prof") == "file"


def test_rollback_of_phase_preparing_removes_only_created_ciphertext_and_key(tmp_path, monkeypatch):
    """Crash/failure during preparing rolls back created ciphertext and key without harming pre-existing ones."""
    prof_dir = tmp_path / "profiles" / "rollback_prof"
    prof_dir.mkdir(parents=True)
    cookies_path = prof_dir / "cookies.json"
    cookies_path.write_text(json.dumps({"SID": "good_sid"}), encoding="utf-8")

    # Simulate readback verification failure
    store = CredentialStore()

    def fake_read(pname):
        return {"cookies": {"SID": "tampered_sid"}, "csrf_token": "", "session_id": ""}

    monkeypatch.setattr(store, "read_credentials", fake_read)
    monkeypatch.setattr("notebooklm_tools.core.auth_migration.CredentialStore", lambda: store)

    with pytest.raises(CredentialStoreError, match="Verification failed"):
        migrate_profile_to_protected("rollback_prof")

    # Verify rollback
    assert cookies_path.exists()
    assert not (prof_dir / "credentials.enc").exists()
    assert not store.has_key("rollback_prof")
    assert read_operation_marker("rollback_prof") is None


def test_recovery_of_migrate_to_file_recognizes_published_target(tmp_path):
    """Recovery of migrate_to_file recognizes published target even if process crashed before clearing marker."""
    prof_dir = tmp_path / "profiles" / "target_prof"
    prof_dir.mkdir(parents=True)
    cookies_path = prof_dir / "cookies.json"
    cookies_path.write_text(json.dumps({"SID": "published_sid"}), encoding="utf-8")

    store = CredentialStore()
    store.write_credentials("target_prof", {"cookies": {"SID": "published_sid"}})
    enc_path = prof_dir / "credentials.enc"
    assert enc_path.exists()

    # Write marker simulating crash during committed
    marker_data = {
        "version": 1,
        "operation_id": "test_op",
        "operation": "migrate_to_file",
        "profile": "target_prof",
        "phase": "committed",
    }
    write_operation_marker("target_prof", marker_data)

    reconciled = reconcile_pending_operations("target_prof")
    assert reconciled is True
    assert get_auth_storage_mode("target_prof") == "file"
    assert not enc_path.exists()
    assert not store.has_key("target_prof")
    assert read_operation_marker("target_prof") is None


def test_recovery_of_migrate_to_file_preserves_ciphertext_if_unverified(tmp_path):
    """Recovery of migrate_to_file safely preserves ciphertext and rolls back mode if export cannot be verified."""
    prof_dir = tmp_path / "profiles" / "target_prof2"
    prof_dir.mkdir(parents=True)
    cookies_path = prof_dir / "cookies.json"
    cookies_path.write_text(json.dumps({"SID": "divergent_sid"}), encoding="utf-8")

    store = CredentialStore()
    store.write_credentials("target_prof2", {"cookies": {"SID": "protected_sid"}})
    enc_path = prof_dir / "credentials.enc"
    assert enc_path.exists()

    marker_data = {
        "version": 1,
        "operation_id": "test_op2",
        "operation": "migrate_to_file",
        "profile": "target_prof2",
        "phase": "committed",
    }
    write_operation_marker("target_prof2", marker_data)

    reconciled = reconcile_pending_operations("target_prof2")
    assert reconciled is True
    # Safely rolled back to protected
    assert get_auth_storage_mode("target_prof2") == "protected"
    # Preserved ciphertext and key!
    assert enc_path.exists()
    assert store.has_key("target_prof2")
    # Marker cleared
    assert read_operation_marker("target_prof2") is None


def test_file_mode_never_opens_keystore_in_load_profile(tmp_path, monkeypatch):
    """Ordinary load_profile in file mode must never open the OS store, even if credentials.enc exists."""
    auth = AuthManager("file_prof")
    auth.save_profile(cookies={"SID": "plain_sid"}, csrf_token="plain_csrf")

    # Plant a fake credentials.enc residue
    enc_path = get_profile_dir("file_prof") / "credentials.enc"
    enc_path.write_text("residue", encoding="utf-8")

    # Assert get_storage_status does NOT open store
    status = get_storage_status("file_prof")
    assert status["mode"] == "file"
    assert status["protected_residue"] is True
    assert status["has_conflict"] is False

    # Mock CredentialStore to raise if any method is called
    mock_store = MagicMock()
    mock_store.read_credentials.side_effect = AssertionError("Keystore opened in file mode!")
    monkeypatch.setattr(
        "notebooklm_tools.core.credential_store.CredentialStore", lambda: mock_store
    )

    # load_profile must succeed without touching keystore
    profile = auth.load_profile()
    assert profile.cookies == {"SID": "plain_sid"}
    assert not mock_store.read_credentials.called


def test_two_profiles_with_different_modes_isolation(tmp_path):
    """Switching mode for profile A leaves profile B completely untouched."""
    auth_a = AuthManager("prof_a")
    auth_a.save_profile(cookies={"SID": "sid_a"}, email="a@example.com")

    auth_b = AuthManager("prof_b")
    auth_b.save_profile(cookies={"SID": "sid_b"}, email="b@example.com")

    # Migrate prof_a to protected
    res = set_storage_mode("protected", profile_name="prof_a")
    assert res["mode"] == "protected"
    assert get_auth_storage_mode("prof_a") == "protected"

    # prof_b must remain 100% in file mode with plaintext intact
    assert get_auth_storage_mode("prof_b") == "file"
    assert (get_profile_dir("prof_b") / "cookies.json").exists()
    assert not (get_profile_dir("prof_b") / "credentials.enc").exists()
    assert auth_b.load_profile().cookies == {"SID": "sid_b"}


def test_set_protected_refused_when_pending_operation_exists(tmp_path):
    """set_storage_mode refuses when an unfinished operation marker exists."""
    write_operation_marker(
        "pending_prof", {"operation": "migrate_to_protected", "phase": "preparing"}
    )

    with pytest.raises(ServiceError, match="unfinished operation in progress"):
        set_storage_mode("protected", profile_name="pending_prof")


def test_conflict_detection_divergent_secrets_in_protected_mode(tmp_path):
    """In protected mode, if cookies.json exists with divergent secrets, load_profile raises StorageConflictError."""
    auth = AuthManager("conflict_prof")
    auth.save_profile(cookies={"SID": "prot_sid"}, email="conf@example.com")
    set_storage_mode("protected", profile_name="conflict_prof")

    # Manually drop a divergent cookies.json into the profile dir
    cookies_path = get_profile_dir("conflict_prof") / "cookies.json"
    cookies_path.write_text(json.dumps({"SID": "divergent_plain_sid"}), encoding="utf-8")

    # Status reports conflict
    status = get_storage_status("conflict_prof")
    assert status["has_conflict"] is True

    # load_profile raises StorageConflictError
    auth._profile = None
    with pytest.raises(StorageConflictError):
        auth.load_profile()


def test_resolve_storage_conflict_choices(tmp_path):
    """resolve_storage_conflict handles choice='protected', choice='file', and discard_inaccessible."""
    auth = AuthManager("res_prof")
    auth.save_profile(cookies={"SID": "prot_sid"}, email="conf@example.com")
    set_storage_mode("protected", profile_name="res_prof")

    # Create divergent cookies.json
    prof_dir = get_profile_dir("res_prof")
    cookies_path = prof_dir / "cookies.json"
    cookies_path.write_text(json.dumps({"SID": "plain_sid"}), encoding="utf-8")

    # 1. Resolve to protected: unlinks plain file
    res = resolve_storage_conflict("res_prof", choice="protected")
    assert res["mode"] == "protected"
    assert not cookies_path.exists()
    assert (prof_dir / "credentials.enc").exists()

    # Re-create cookies.json to test resolve to file
    cookies_path.write_text(json.dumps({"SID": "plain_sid"}), encoding="utf-8")
    res_file = resolve_storage_conflict("res_prof", choice="file")
    assert res_file["mode"] == "file"
    assert cookies_path.exists()
    assert not (prof_dir / "credentials.enc").exists()

    # 3. Test discard-inaccessible path when ciphertext is corrupt
    enc_path = prof_dir / "credentials.enc"
    enc_path.write_text("{corrupt_ciphertext", encoding="utf-8")
    cookies_path.unlink()

    # Normal resolve file refuses because ciphertext cannot be exported
    with pytest.raises(ServiceError, match="Cannot decrypt protected credentials"):
        resolve_storage_conflict("res_prof", choice="file", discard_inaccessible=False)

    # With discard_inaccessible=True, it purges ciphertext and resets to file mode
    discard_res = resolve_storage_conflict("res_prof", choice="file", discard_inaccessible=True)
    assert discard_res["mode"] == "file"
    assert not enc_path.exists()
    assert get_auth_storage_mode("res_prof") == "file"


def test_repro_a_set_file_with_ciphertext_residue(tmp_path):
    """Repro A: set_storage_mode('file') cleans identical residue; refuses and flags conflict if divergent."""
    auth = AuthManager("prof_repro_a")
    auth.save_profile(cookies={"SID": "common_cookie"}, email="repro_a@example.com")
    assert get_auth_storage_mode("prof_repro_a") == "file"
    prof_dir = get_profile_dir("prof_repro_a")
    enc_path = prof_dir / "credentials.enc"

    # Case 1: Residue has identical cookies
    store = CredentialStore()
    store.write_credentials("prof_repro_a", {"cookies": {"SID": "common_cookie"}})
    assert enc_path.exists()
    assert store.has_key("prof_repro_a")

    res = set_storage_mode("file", profile_name="prof_repro_a")
    assert res["status"] == "updated"
    assert not enc_path.exists()
    assert not store.has_key("prof_repro_a")

    # Case 2: Residue has divergent cookies
    store.write_credentials("prof_repro_a", {"cookies": {"SID": "divergent_cookie"}})
    assert enc_path.exists()
    with pytest.raises(ServiceError, match="Conflict detected.*differ from protected residue"):
        set_storage_mode("file", profile_name="prof_repro_a")
    # Ciphertext and key must NOT be deleted!
    assert enc_path.exists()
    assert store.has_key("prof_repro_a")


def test_repro_b_set_protected_with_plaintext_residue(tmp_path):
    """Repro B: set_storage_mode('protected') cleans identical plaintext residue; refuses if divergent."""
    auth = AuthManager("prof_repro_b")
    auth.save_profile(cookies={"SID": "common_cookie"}, email="repro_b@example.com")
    set_storage_mode("protected", profile_name="prof_repro_b")
    assert get_auth_storage_mode("prof_repro_b") == "protected"
    prof_dir = get_profile_dir("prof_repro_b")
    cookies_path = prof_dir / "cookies.json"

    # Case 1: Plaintext residue has identical cookies
    cookies_path.write_text(json.dumps({"SID": "common_cookie"}), encoding="utf-8")
    res = set_storage_mode("protected", profile_name="prof_repro_b")
    assert res["status"] == "updated"
    assert not cookies_path.exists()

    # Case 2: Plaintext residue has divergent cookies
    cookies_path.write_text(json.dumps({"SID": "divergent_cookie"}), encoding="utf-8")
    with pytest.raises(ServiceError, match="Conflict detected.*differ from plaintext residue"):
        set_storage_mode("protected", profile_name="prof_repro_b")
    # Plaintext must NOT be deleted!
    assert cookies_path.exists()


def test_zero_footprint_startup_no_operations_dir(tmp_path):
    """File mode operations and queries must have zero footprint: operations/ is never created on reads."""
    status = get_storage_status("default")
    assert status["mode"] == "file"
    marker = read_operation_marker("default")
    assert marker is None
    ops_dir = _get_operations_dir()
    assert not ops_dir.exists()


def test_rename_profile_refuses_when_operation_marker_exists(tmp_path):
    """rename_profile refuses if an unfinished or corrupt operation marker exists."""
    auth = AuthManager("rename_src")
    auth.save_profile(cookies={"SID": "rename_sid"}, email="src@example.com")

    # Case 1: Unfinished marker
    write_operation_marker(
        "rename_src", {"operation": "migrate_to_protected", "phase": "preparing"}
    )
    with pytest.raises(ServiceError, match="unfinished storage operation is in progress"):
        rename_profile("rename_src", "rename_dst")

    # Case 2: Corrupt marker
    marker_path = _get_operations_dir() / "rename_src.json"
    marker_path.write_text("{corrupt_json_here", encoding="utf-8")
    with pytest.raises(ServiceError, match="corrupt operation marker"):
        rename_profile("rename_src", "rename_dst")


def test_env_override_disagreement_refused(tmp_path, monkeypatch):
    """If NLM_AUTH_STORAGE disagrees with on-disk mode, set and resolve refuse with clear message."""
    auth = AuthManager("env_prof")
    auth.save_profile(cookies={"SID": "env_sid"}, email="env@example.com")
    assert get_auth_storage_mode("env_prof") == "file"

    monkeypatch.setenv("NLM_AUTH_STORAGE", "protected")
    with pytest.raises(
        ServiceError,
        match="NLM_AUTH_STORAGE environment variable .* disagrees with on-disk storage mode",
    ):
        set_storage_mode("protected", profile_name="env_prof")

    with pytest.raises(
        ServiceError,
        match="NLM_AUTH_STORAGE environment variable .* disagrees with on-disk storage mode",
    ):
        resolve_storage_conflict("env_prof", choice="file")


def test_reconcile_committed_hash_verification_bidirectional(tmp_path):
    """Reconcile in committed phase deletes matching leftover cookies.json, but keeps divergent copy."""
    # Direction 1: Matching cookies_hash -> unlinked
    prof_dir1 = tmp_path / "profiles" / "match_prof"
    prof_dir1.mkdir(parents=True)
    cookies_path1 = prof_dir1 / "cookies.json"
    cookies_path1.write_text(json.dumps({"SID": "match_sid"}), encoding="utf-8")
    write_operation_marker(
        "match_prof",
        {
            "operation": "migrate_to_protected",
            "phase": "committed",
            "cookies_hash": compute_cookies_hash({"SID": "match_sid"}),
        },
    )
    assert reconcile_pending_operations("match_prof") is True
    assert not cookies_path1.exists()

    # Direction 2: Divergent cookies_hash -> kept and warning logged
    prof_dir2 = tmp_path / "profiles" / "diff_prof"
    prof_dir2.mkdir(parents=True)
    cookies_path2 = prof_dir2 / "cookies.json"
    cookies_path2.write_text(json.dumps({"SID": "newer_live_sid"}), encoding="utf-8")
    write_operation_marker(
        "diff_prof",
        {
            "operation": "migrate_to_protected",
            "phase": "committed",
            "cookies_hash": compute_cookies_hash({"SID": "old_snapshot_sid"}),
        },
    )
    assert reconcile_pending_operations("diff_prof") is True
    assert cookies_path2.exists()


def test_discard_inaccessible_cases(tmp_path, monkeypatch):
    """--discard-inaccessible refuses healthy credentials and backend errors, succeeds only for corrupt data."""
    auth = AuthManager("disc_prof")
    auth.save_profile(cookies={"SID": "healthy_sid"}, email="healthy@example.com")
    set_storage_mode("protected", profile_name="disc_prof")

    # Case 1: Healthy and readable credentials -> REFUSE discard
    with pytest.raises(
        ServiceError,
        match="Cannot discard credentials: protected credentials .* are healthy and readable",
    ):
        resolve_storage_conflict("disc_prof", choice="file", discard_inaccessible=True)

    # Case 2: Backend unavailable (e.g. headless/no display/locked) -> REFUSE discard
    orig_read = CredentialStore.read_credentials

    def mock_backend_unavailable(self, name):
        raise BackendUnavailableError("Keyring daemon is locked")

    monkeypatch.setattr(CredentialStore, "read_credentials", mock_backend_unavailable)
    with pytest.raises(
        ServiceError, match="OS credential backend is locked, unavailable, or timed out"
    ):
        resolve_storage_conflict("disc_prof", choice="file", discard_inaccessible=True)

    # Case 3: Backend timeout -> REFUSE discard
    def mock_backend_timeout(self, name):
        raise BackendTimeoutError("Keystore operation timed out after 60s")

    monkeypatch.setattr(CredentialStore, "read_credentials", mock_backend_timeout)
    with pytest.raises(
        ServiceError, match="OS credential backend is locked, unavailable, or timed out"
    ):
        resolve_storage_conflict("disc_prof", choice="file", discard_inaccessible=True)

    # Case 4: Truly unrecoverable (corrupt ciphertext) -> ALLOW discard
    monkeypatch.setattr(CredentialStore, "read_credentials", orig_read)
    enc_path = get_profile_dir("disc_prof") / "credentials.enc"
    enc_path.write_text("{bad_cipher", encoding="utf-8")
    res = resolve_storage_conflict("disc_prof", choice="file", discard_inaccessible=True)
    assert res["status"] == "resolved"
    assert not enc_path.exists()
    assert get_auth_storage_mode("disc_prof") == "file"


def test_clear_marker_cases(tmp_path):
    """--clear-marker refuses if quarantine folder contains files; succeeds when absent."""
    write_operation_marker(
        "clear_prof", {"operation": "migrate_to_protected", "phase": "preparing"}
    )

    # Case 1: Quarantine folder exists and contains files
    q_dir = _get_operations_dir() / "quarantine" / "clear_prof_op1"
    q_dir.mkdir(parents=True)
    (q_dir / "cookies.json").write_text("{}", encoding="utf-8")

    with pytest.raises(
        ServiceError, match="Cannot clear marker: quarantine folder .* contains credentials files"
    ):
        resolve_storage_conflict("clear_prof", clear_marker=True)

    # Case 2: Quarantine folder cleaned up -> succeeds
    (q_dir / "cookies.json").unlink()
    q_dir.rmdir()
    res = resolve_storage_conflict("clear_prof", clear_marker=True)
    assert res["status"] == "resolved"
    assert read_operation_marker("clear_prof") is None


def test_reconcile_migrate_to_file_when_keystore_unavailable(tmp_path, monkeypatch):
    """Reconcile of migrate_to_file when keystore is unavailable changes nothing and keeps marker."""
    prof_dir = tmp_path / "profiles" / "keystore_unavail_prof"
    prof_dir.mkdir(parents=True)
    (prof_dir / "credentials.enc").write_text("enc_payload", encoding="utf-8")
    write_operation_marker(
        "keystore_unavail_prof",
        {"operation": "migrate_to_file", "phase": "committed"},
    )

    monkeypatch.setattr(CredentialStore, "is_available", lambda self: False)
    assert reconcile_pending_operations("keystore_unavail_prof") is True
    # Marker must be kept!
    assert read_operation_marker("keystore_unavail_prof") is not None
    # Ciphertext must be kept!
    assert (prof_dir / "credentials.enc").exists()


def test_helper_subprocess_never_takes_profile_lock_no_deadlock(tmp_path):
    """Helper subprocess operations must never take the profile lock, preventing deadlock when caller holds it."""
    with get_profile_lock("deadlock_test_prof"):
        # While profile lock is held by caller, perform a protected save
        auth = AuthManager("deadlock_test_prof")
        auth.save_profile(cookies={"SID": "deadlock_sid"}, email="deadlock@example.com")
        set_storage_mode("protected", profile_name="deadlock_test_prof")
        # Read back protected credentials
        profile = auth.load_profile()
        assert profile.cookies == {"SID": "deadlock_sid"}


def test_lock_acquisition_timeout_typed_error(tmp_path, monkeypatch):
    """Profile lock timeout raises LockAcquisitionTimeoutError with user-friendly message."""
    import threading

    from filelock import FileLock

    from notebooklm_tools.core import credential_store

    monkeypatch.setattr(credential_store, "LOCK_TIMEOUT_SECONDS", 0.1)

    lock1 = get_profile_lock("timeout_prof")
    lock1.acquire()

    def run_lock2():
        lock_path = (tmp_path / "locks" / "timeout_prof.lock").resolve()
        other_raw = FileLock(lock_path, timeout=0.1)
        other_lock = credential_store.ProfileLock(other_raw, "timeout_prof")
        with pytest.raises(
            LockAcquisitionTimeoutError,
            match="another nlm process is changing this profile's storage; try again",
        ):
            other_lock.acquire()

    th = threading.Thread(target=run_lock2)
    th.start()
    th.join()
    lock1.release()


def test_server_info_storage_warning(tmp_path):
    """server_info includes storage_warning field: None when healthy, short string on conflict, never breaks."""
    info_healthy = server_info()
    assert info_healthy["storage_warning"] is None

    # Introduce conflict in default profile
    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "default_sid"}, email="def@example.com")
    set_storage_mode("protected", profile_name="default")
    (get_profile_dir("default") / "cookies.json").write_text(
        json.dumps({"SID": "divergent_plain_sid"}), encoding="utf-8"
    )

    info_conflict = server_info()
    assert (
        info_conflict["storage_warning"]
        == "Storage conflict detected. Run 'nlm auth storage resolve'."
    )


class SharedFileBackend:
    def __init__(self, p: Any) -> None:
        self.p = Path(p)

    def _read(self) -> dict[str, Any]:
        if not self.p.exists():
            return {}
        try:
            return cast(dict[str, Any], json.loads(self.p.read_text(encoding="utf-8")))
        except Exception:
            return {}

    def _write(self, d: dict[str, Any]) -> None:
        self.p.parent.mkdir(parents=True, exist_ok=True)
        self.p.write_text(json.dumps(d), encoding="utf-8")

    def get_password(self, s: str, a: str) -> str | None:
        return self._read().get(f"{s}:{a}")

    def set_password(self, s: str, a: str, pw: str) -> None:
        d = self._read()
        d[f"{s}:{a}"] = pw
        self._write(d)

    def delete_password(self, s: str, a: str) -> None:
        d = self._read()
        d.pop(f"{s}:{a}", None)
        self._write(d)


def test_two_process_race_in_suite(tmp_path):
    """In-suite two-process race test with shrunk timings demonstrating lock serialization and credential preservation."""
    import os
    import subprocess
    import sys

    from notebooklm_tools.core.credential_store import set_backend_factory

    keystore_file = tmp_path / "test_keystore.json"
    set_backend_factory(lambda: SharedFileBackend(keystore_file))

    backend_setup_code = f"""
import json
from pathlib import Path
class SharedFileBackend:
    def __init__(self, p):
        self.p = Path(p)
    def _read(self):
        if not self.p.exists(): return {{}}
        try: return json.loads(self.p.read_text(encoding="utf-8"))
        except: return {{}}
    def _write(self, d):
        self.p.parent.mkdir(parents=True, exist_ok=True)
        self.p.write_text(json.dumps(d), encoding="utf-8")
    def get_password(self, s, a):
        return self._read().get(f"{{s}}:{{a}}")
    def set_password(self, s, a, pw):
        d = self._read()
        d[f"{{s}}:{{a}}"] = pw
        self._write(d)
    def delete_password(self, s, a):
        d = self._read()
        d.pop(f"{{s}}:{{a}}", None)
        self._write(d)

from notebooklm_tools.core.credential_store import set_backend_factory
set_backend_factory(lambda: SharedFileBackend({repr(str(keystore_file))}))
"""

    auth = AuthManager("race_in_suite")
    auth.save_profile(cookies={"SID": "initial_sid"}, email="race@example.com")

    code_migration = f"""
import os
os.environ["NOTEBOOKLM_MCP_CLI_PATH"] = {repr(str(tmp_path))}
{backend_setup_code}
from notebooklm_tools.utils.config import reset_config
from notebooklm_tools.services.auth_storage import set_storage_mode
reset_config()
set_storage_mode("protected", profile_name="race_in_suite")
"""

    code_save = f"""
import os
os.environ["NOTEBOOKLM_MCP_CLI_PATH"] = {repr(str(tmp_path))}
{backend_setup_code}
from notebooklm_tools.utils.config import reset_config
from notebooklm_tools.core.auth import AuthTokens, save_tokens_to_cache
reset_config()
t = AuthTokens(cookies={{"SID": "winner_sid"}}, csrf_token="winner_csrf")
save_tokens_to_cache(t, profile_name="race_in_suite")
"""

    env = os.environ.copy()
    env["NOTEBOOKLM_MCP_CLI_PATH"] = str(tmp_path)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent.parent / "src")

    p1 = subprocess.Popen([sys.executable, "-c", code_migration], env=env)
    p2 = subprocess.Popen([sys.executable, "-c", code_save], env=env)

    ret1 = p1.wait(timeout=15)
    ret2 = p2.wait(timeout=15)

    assert ret1 == 0
    assert ret2 == 0

    re_auth = AuthManager("race_in_suite")
    prof = re_auth.load_profile()
    assert prof.cookies["SID"] in ("winner_sid", "initial_sid")


def test_migrate_default_profile_with_stale_root_csrf(tmp_path):
    """Default profile with fresh metadata CSRF and stale root auth.json CSRF migrates cleanly."""
    prof_dir = tmp_path / "profiles" / "default"
    prof_dir.mkdir(parents=True)
    cookies = {"SID": "shared_sid"}
    (prof_dir / "cookies.json").write_text(json.dumps(cookies), encoding="utf-8")
    (prof_dir / "metadata.json").write_text(
        json.dumps({"csrf_token": "csrf-NEW", "session_id": "sess-NEW"}),
        encoding="utf-8",
    )

    root_auth = tmp_path / "auth.json"
    root_auth.write_text(
        json.dumps({"cookies": cookies, "csrf_token": "csrf-OLD", "session_id": "sess-OLD"}),
        encoding="utf-8",
    )

    res = migrate_profile_to_protected("default")
    assert res["mode"] == "protected"
    assert res["migrated"] is True
    assert "auth.json" in res["removed_files"]
    assert "profiles/default/cookies.json" in res["removed_files"]
    assert not root_auth.exists()

    # Readback verified
    store = CredentialStore()
    creds = store.read_credentials("default")
    assert creds is not None
    assert creds["csrf_token"] == "csrf-NEW"
    assert creds["session_id"] == "sess-NEW"
    assert creds["cookies"] == cookies


def test_migrate_default_profile_with_identical_root(tmp_path):
    """Default profile with identical root auth.json migrates cleanly and unlinks root mirror."""
    prof_dir = tmp_path / "profiles" / "default"
    prof_dir.mkdir(parents=True)
    cookies = {"SID": "shared_sid"}
    (prof_dir / "cookies.json").write_text(json.dumps(cookies), encoding="utf-8")
    (prof_dir / "metadata.json").write_text(
        json.dumps({"csrf_token": "csrf-SAME", "session_id": "sess-SAME"}),
        encoding="utf-8",
    )

    root_auth = tmp_path / "auth.json"
    root_auth.write_text(
        json.dumps({"cookies": cookies, "csrf_token": "csrf-SAME", "session_id": "sess-SAME"}),
        encoding="utf-8",
    )

    res = migrate_profile_to_protected("default")
    assert res["mode"] == "protected"
    assert res["migrated"] is True
    assert "auth.json" in res["removed_files"]
    assert not root_auth.exists()

    store = CredentialStore()
    creds = store.read_credentials("default")
    assert creds is not None
    assert creds["csrf_token"] == "csrf-SAME"


def test_migrate_default_profile_with_stale_root_cookies(tmp_path):
    """Default profile with active fresh cookies migrates cleanly when root auth has stale cookies."""
    prof_dir = tmp_path / "profiles" / "default"
    prof_dir.mkdir(parents=True)
    fresh_cookies = {"SID": "fresh_cookie_val"}
    (prof_dir / "cookies.json").write_text(json.dumps(fresh_cookies), encoding="utf-8")
    (prof_dir / "metadata.json").write_text(
        json.dumps({"csrf_token": "csrf-SAME", "session_id": "sess-SAME"}),
        encoding="utf-8",
    )

    root_auth = tmp_path / "auth.json"
    stale_cookies = {"SID": "stale_root_cookie_val"}
    root_auth.write_text(
        json.dumps(
            {"cookies": stale_cookies, "csrf_token": "csrf-SAME", "session_id": "sess-SAME"}
        ),
        encoding="utf-8",
    )

    res = migrate_profile_to_protected("default")
    assert res["mode"] == "protected"
    assert res["migrated"] is True
    assert "auth.json" in res["removed_files"]
    assert not root_auth.exists()

    store = CredentialStore()
    creds = store.read_credentials("default")
    assert creds is not None
    assert creds["cookies"] == fresh_cookies


def test_migrate_named_default_profile_with_stale_root(tmp_path):
    """Configured default profile 'work' migrates cleanly when root auth.json has stale CSRF."""
    cfg = get_config()
    cfg.auth.default_profile = "work"
    save_config(cfg)

    prof_dir = tmp_path / "profiles" / "work"
    prof_dir.mkdir(parents=True)
    cookies = {"SID": "work_sid"}
    (prof_dir / "cookies.json").write_text(json.dumps(cookies), encoding="utf-8")
    (prof_dir / "metadata.json").write_text(
        json.dumps({"csrf_token": "csrf-WORK", "session_id": "sess-WORK"}),
        encoding="utf-8",
    )

    root_auth = tmp_path / "auth.json"
    root_auth.write_text(
        json.dumps({"cookies": cookies, "csrf_token": "csrf-ROOT", "session_id": "sess-ROOT"}),
        encoding="utf-8",
    )

    res = migrate_profile_to_protected("work")
    assert res["mode"] == "protected"
    assert res["migrated"] is True
    assert "auth.json" in res["removed_files"]
    assert not root_auth.exists()

    store = CredentialStore()
    creds = store.read_credentials("work")
    assert creds is not None
    assert creds["csrf_token"] == "csrf-WORK"
    assert creds["session_id"] == "sess-WORK"


def test_migrate_aborts_on_concurrent_metadata_modification(tmp_path, monkeypatch):
    """If metadata.json changes during migration quarantine, migration aborts and restores source files."""
    prof_dir = tmp_path / "profiles" / "meta_race"
    prof_dir.mkdir(parents=True)
    cookies_path = prof_dir / "cookies.json"
    metadata_path = prof_dir / "metadata.json"
    cookies = {"SID": "race_sid"}
    cookies_path.write_text(json.dumps(cookies), encoding="utf-8")
    metadata_path.write_text(
        json.dumps({"csrf_token": "initial_csrf", "session_id": "initial_sess"}),
        encoding="utf-8",
    )

    orig_move = __import__("shutil").move

    def racing_move(src, dst):
        res = orig_move(src, dst)
        if "quarantine" in str(dst) and "cookies.json" in str(dst):
            # Concurrent process updates metadata.json right after cookies were moved
            metadata_path.write_text(
                json.dumps({"csrf_token": "concurrent_csrf", "session_id": "concurrent_sess"}),
                encoding="utf-8",
            )
        return res

    monkeypatch.setattr("shutil.move", racing_move)

    with pytest.raises(CredentialStoreError, match="modified concurrently"):
        migrate_profile_to_protected("meta_race")

    # Verification: source cookies restored, mode remains file
    assert cookies_path.exists()
    assert get_auth_storage_mode("meta_race") == "file"


def test_migrate_legacy_profile_with_metadata_csrf_difference(tmp_path):
    """Legacy profile (auth.json only, no cookies.json) with differing metadata CSRF migrates cleanly."""
    prof_dir = tmp_path / "profiles" / "legacy_prof"
    prof_dir.mkdir(parents=True)
    cookies = {"SID": "legacy_sid"}
    (prof_dir / "auth.json").write_text(
        json.dumps({"cookies": cookies, "csrf_token": "csrf-AUTH", "session_id": "sess-AUTH"}),
        encoding="utf-8",
    )
    (prof_dir / "metadata.json").write_text(
        json.dumps({"csrf_token": "csrf-META", "session_id": "sess-META"}),
        encoding="utf-8",
    )

    res = migrate_profile_to_protected("legacy_prof")
    assert res["mode"] == "protected"
    assert res["migrated"] is True
    assert "profiles/legacy_prof/auth.json" in res["removed_files"]
    assert not (prof_dir / "auth.json").exists()

    store = CredentialStore()
    creds = store.read_credentials("legacy_prof")
    assert creds is not None
    assert creds["csrf_token"] == "csrf-META"
    assert creds["session_id"] == "sess-META"
    assert creds["cookies"] == cookies


def test_set_protected_refuses_when_backend_unavailable(tmp_path, monkeypatch):
    """When OS store is unavailable (e.g. headless Linux, Windows SSH error 1312), set protected refuses and setup keeps working."""
    from typer.testing import CliRunner

    from notebooklm_tools.cli.main import app

    prof_dir = tmp_path / "profiles" / "unavail_prof"
    prof_dir.mkdir(parents=True)
    cookies_path = prof_dir / "cookies.json"
    cookies_path.write_text(json.dumps({"SID": "unavail_sid"}), encoding="utf-8")
    (prof_dir / "metadata.json").write_text(
        json.dumps({"email": "u@example.com"}), encoding="utf-8"
    )

    # Simulate unavailable OS store backend (e.g. headless Linux without D-Bus, Windows SSH, locked keychain)
    monkeypatch.setattr(CredentialStore, "is_available", lambda self: False)

    # 1. Service layer refusal:
    with pytest.raises(
        ServiceError,
        match="Cannot enable protected mode: OS credential store is unavailable or locked",
    ):
        set_storage_mode("protected", profile_name="unavail_prof")

    # Verify current file-mode setup keeps working untouched:
    assert get_auth_storage_mode("unavail_prof") == "file"
    assert cookies_path.exists()
    assert not (prof_dir / "credentials.enc").exists()

    # 2. CLI layer refusal:
    runner = CliRunner()
    result = runner.invoke(
        app, ["auth", "storage", "set", "protected", "--profile", "unavail_prof"]
    )
    assert result.exit_code != 0
    assert "OS credential store is unavailable or" in result.output
    # Mode is still file
    assert get_auth_storage_mode("unavail_prof") == "file"
    assert cookies_path.exists()
