"""Tests for core credential store: encryption, installation identity, locks, and operations."""

import json
import os

import pytest

from notebooklm_tools.core.credential_store import (
    MAX_KEYSTORE_ITEM_LENGTH,
    SERVICE_NAME,
    BackendMismatchError,
    CorruptCiphertextError,
    CredentialStore,
    InstallationPathMismatchError,
    MissingKeyError,
    OversizedCiphertextError,
    SymlinkPathRejectedError,
    UnsupportedVersionError,
    check_installation_identity,
    get_installation_identity,
    relocate_installation,
)
from notebooklm_tools.utils.config import get_profile_dir, get_storage_dir


def test_installation_identity_generation_and_persistence():
    """Installation identity is generated and persisted in installation.json."""
    storage_dir = get_storage_dir()
    identity = get_installation_identity(storage_dir)

    assert identity.installation_id
    assert len(identity.installation_id) >= 16
    assert identity.canonical_root == str(storage_dir.resolve())

    # Same identity returned on subsequent calls
    identity2 = get_installation_identity(storage_dir)
    assert identity2.installation_id == identity.installation_id


def test_installation_path_mismatch_blocks_mutation(fake_credential_store):
    """A moved or copied root with path mismatch blocks key mutation."""
    storage_dir = get_storage_dir()
    _ = get_installation_identity(storage_dir)

    # Manually tamper canonical root in installation.json to simulate an unconfirmed move/copy
    install_file = storage_dir / "installation.json"
    data = json.loads(install_file.read_text(encoding="utf-8"))
    data["canonical_root"] = "/some/different/path"
    install_file.write_text(json.dumps(data))

    store = CredentialStore()
    payload = {"cookies": {"SID": "123"}, "csrf_token": "token1", "session_id": "sess1"}

    # Mutation must be blocked!
    with pytest.raises(InstallationPathMismatchError):
        store.write_credentials("test_profile", payload)

    with pytest.raises(InstallationPathMismatchError):
        store.delete_credentials("test_profile")

    # Explicit relocation adopts the new root
    relocate_installation(storage_dir)
    # Now mutation succeeds
    store.write_credentials("test_profile", payload)
    read_back = store.read_credentials("test_profile")
    assert read_back == payload


def test_two_profiles_with_isolated_keys_and_payloads(fake_credential_store):
    """Two profiles have distinct keys and distinct payloads."""
    store = CredentialStore()

    payload_a = {"cookies": {"SID": "alpha"}, "csrf_token": "csrf_a", "session_id": "sess_a"}
    payload_b = {"cookies": {"SID": "beta"}, "csrf_token": "csrf_b", "session_id": "sess_b"}

    store.write_credentials("profile_a", payload_a)
    store.write_credentials("profile_b", payload_b)

    assert store.read_credentials("profile_a") == payload_a
    assert store.read_credentials("profile_b") == payload_b

    # Verify both have credentials.enc
    assert (get_profile_dir("profile_a") / "credentials.enc").exists()
    assert (get_profile_dir("profile_b") / "credentials.enc").exists()


def test_two_installations_isolated(fake_credential_store, tmp_path):
    """Same profile name under two different installation IDs has separate keys in keystore."""
    dir_1 = tmp_path / "inst1"
    dir_2 = tmp_path / "inst2"

    store_1 = CredentialStore(storage_dir=dir_1)
    store_2 = CredentialStore(storage_dir=dir_2)

    id_1 = get_installation_identity(dir_1).installation_id
    id_2 = get_installation_identity(dir_2).installation_id
    assert id_1 != id_2

    payload_1 = {"cookies": {"SID": "from_inst_1"}}
    payload_2 = {"cookies": {"SID": "from_inst_2"}}

    store_1.write_credentials("shared_name", payload_1)
    store_2.write_credentials("shared_name", payload_2)

    assert len(fake_credential_store._store) == 2
    # Verify separate accounts under service
    accounts = [acc for (srv, acc) in fake_credential_store._store]
    assert f"{id_1}:shared_name" in accounts
    assert f"{id_2}:shared_name" in accounts


def test_20kib_payload_and_unicode_support(fake_credential_store):
    """Large 20 KiB payload and Unicode characters encrypt and decrypt correctly."""
    store = CredentialStore()

    large_unicode_data = {
        "cookies": {"SID": "val_" + ("日本語_🔒_emoji_" * 500)},
        "csrf_token": "csrf_" + ("café_crème_über_" * 300),
        "session_id": "sess_" + ("X" * 15000),
    }

    store.write_credentials("large_prof", large_unicode_data)
    read_back = store.read_credentials("large_prof")
    assert read_back == large_unicode_data


def test_keystore_holds_only_44_char_key_not_payload(fake_credential_store):
    """OS keystore must hold ONLY the 44-character base64 key, never payload."""
    store = CredentialStore()
    payload = {"cookies": {"SID": "secret_sid_val"}, "csrf_token": "csrf", "session_id": "sess"}

    store.write_credentials("key_size_prof", payload)

    # Inspect what was stored in the backend
    items = list(fake_credential_store._store.items())
    assert len(items) == 1
    (srv, acc), key_val = items[0]
    assert srv == "notebooklm-mcp-cli.credentials.v1"
    assert "key_size_prof" in acc
    # Key MUST be 44 characters (256-bit base64)
    assert len(key_val) == 44
    assert len(key_val) <= MAX_KEYSTORE_ITEM_LENGTH


def test_corrupt_or_truncated_ciphertext_fails_closed(fake_credential_store):
    """Corrupt or truncated ciphertext raises CorruptCiphertextError."""
    store = CredentialStore()
    payload = {"cookies": {"SID": "123"}}
    store.write_credentials("corrupt_prof", payload)

    enc_file = get_profile_dir("corrupt_prof") / "credentials.enc"

    # Truncate file
    enc_file.write_bytes(b"truncated")
    with pytest.raises(CorruptCiphertextError):
        store.read_credentials("corrupt_prof")

    # Corrupt valid JSON envelope
    envelope = {
        "version": 1,
        "revision": "rev1",
        "nonce": "bm9uY2UxMjM0NTY=",
        "ciphertext": "YmFkY2lwaGVydGV4dA==",
    }
    enc_file.write_text(json.dumps(envelope))
    with pytest.raises(CorruptCiphertextError):
        store.read_credentials("corrupt_prof")


def test_missing_key_in_keystore_fails_closed(fake_credential_store):
    """If ciphertext exists but OS key is missing, raise MissingKeyError."""
    store = CredentialStore()
    store.write_credentials("missing_key_prof", {"cookies": {"SID": "123"}})

    # Wipe key from store
    fake_credential_store.clear()

    with pytest.raises(MissingKeyError):
        store.read_credentials("missing_key_prof")


def test_existing_ciphertext_with_missing_key_does_not_overwrite(fake_credential_store):
    """If ciphertext exists on disk but key is missing, write_credentials refuses to overwrite."""
    store = CredentialStore()
    store.write_credentials("no_overwrite_prof", {"cookies": {"SID": "original"}})

    # Wipe key from store
    fake_credential_store.clear()

    # Attempting to write new credentials over existing ciphertext with missing key must fail
    with pytest.raises(MissingKeyError) as exc_info:
        store.write_credentials("no_overwrite_prof", {"cookies": {"SID": "new"}})

    assert "missing" in str(exc_info.value).lower()
    # Key must NOT have been generated into the store
    assert len(fake_credential_store._store) == 0


def test_oversized_envelope_rejected(fake_credential_store):
    """Ciphertext envelope larger than 1 MiB is rejected without decrypting."""
    storage_dir = get_storage_dir()
    _ = get_installation_identity(storage_dir)

    enc_file = get_profile_dir("oversize_prof") / "credentials.enc"
    enc_file.parent.mkdir(parents=True, exist_ok=True)
    enc_file.write_bytes(b"A" * (1024 * 1024 + 10))

    store = CredentialStore()
    with pytest.raises(OversizedCiphertextError):
        store.read_credentials("oversize_prof")


def test_unsupported_envelope_version_rejected(fake_credential_store):
    """Envelope with unsupported version raises UnsupportedVersionError."""
    store = CredentialStore()
    store.write_credentials("version_prof", {"cookies": {"SID": "123"}})

    enc_file = get_profile_dir("version_prof") / "credentials.enc"
    envelope = json.loads(enc_file.read_text(encoding="utf-8"))
    envelope["version"] = 99
    enc_file.write_text(json.dumps(envelope))

    with pytest.raises(UnsupportedVersionError):
        store.read_credentials("version_prof")


def test_symlink_paths_rejected(fake_credential_store, tmp_path):
    """Symlinked profile directory or credentials.enc is rejected."""
    store = CredentialStore()
    real_target = tmp_path / "symlink_target"
    real_target.mkdir(parents=True, exist_ok=True)

    symlink_prof = get_profile_dir("symlink_prof")
    if symlink_prof.is_symlink() or symlink_prof.exists():
        if symlink_prof.is_dir() and not symlink_prof.is_symlink():
            import shutil

            shutil.rmtree(symlink_prof)
        else:
            symlink_prof.unlink()

    symlink_prof.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(real_target, symlink_prof)
    except OSError:
        pytest.skip("Symlinks not supported on this platform/filesystem")

    with pytest.raises(SymlinkPathRejectedError):
        store.write_credentials("symlink_prof", {"cookies": {"SID": "123"}})

    with pytest.raises(SymlinkPathRejectedError):
        store.read_credentials("symlink_prof")

    # Clean up directory symlink
    symlink_prof.unlink()

    # Now test symlinked credentials.enc inside a real profile directory
    symlink_prof.mkdir(parents=True, exist_ok=True)
    dummy_enc = tmp_path / "dummy_enc"
    dummy_enc.write_text("{}", encoding="utf-8")
    enc_symlink = symlink_prof / "credentials.enc"
    os.symlink(dummy_enc, enc_symlink)

    with pytest.raises(SymlinkPathRejectedError):
        store.read_credentials("symlink_prof")

    with pytest.raises(SymlinkPathRejectedError):
        store.write_credentials("symlink_prof", {"cookies": {"SID": "123"}})


def test_failed_update_preserves_old_ciphertext(fake_credential_store, monkeypatch):
    """A failed update leaves previous valid ciphertext intact and decryptable."""
    store = CredentialStore()
    initial_payload = {"cookies": {"SID": "initial_value"}}
    store.write_credentials("update_prof", initial_payload)

    # Verify initial read works
    assert store.read_credentials("update_prof") == initial_payload

    # Simulate an error during atomic replacement (e.g. os.replace raises OSError)
    real_replace = os.replace

    def _failing_replace(src, dst):
        if "update_prof" in str(dst):
            raise OSError("Simulated disk error during atomic replace")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", _failing_replace)

    with pytest.raises(OSError):
        store.write_credentials("update_prof", {"cookies": {"SID": "new_failing_value"}})

    # Restore os.replace and check that original ciphertext remains decryptable
    monkeypatch.setattr(os, "replace", real_replace)
    assert store.read_credentials("update_prof") == initial_payload


def test_delete_credentials_removes_key_and_ciphertext(fake_credential_store):
    """delete_credentials removes both the key from the keystore and credentials.enc."""
    store = CredentialStore()
    store.write_credentials("del_prof", {"cookies": {"SID": "123"}})

    assert (get_profile_dir("del_prof") / "credentials.enc").exists()
    assert len(fake_credential_store._store) == 1

    store.delete_credentials("del_prof")

    assert not (get_profile_dir("del_prof") / "credentials.enc").exists()
    assert len(fake_credential_store._store) == 0


def test_concurrent_installation_identity_creation(tmp_path):
    """Multiple concurrent creators get the exact same installation ID without race conditions."""
    import concurrent.futures

    inst_dir = tmp_path / "concurrent_inst"

    def _get_id():
        return get_installation_identity(inst_dir).installation_id

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_get_id) for _ in range(16)]
        results = [f.result() for f in futures]

    assert len(results) == 16
    assert len(set(results)) == 1  # All threads got the exact same ID!
    assert (inst_dir / "installation.json").exists()


def test_readback_first_reuses_existing_key_and_never_duplicates(fake_credential_store):
    """When a key already exists in OS store, write_credentials reuses it and never generates a duplicate."""
    import base64

    store = CredentialStore()
    identity = get_installation_identity()
    account_id = f"{identity.installation_id}:reuse_prof"

    # Pre-populate a valid 32-byte key in keystore (e.g. from an interrupted earlier write)
    initial_raw_key = b"R" * 32
    initial_key_b64 = base64.b64encode(initial_raw_key).decode("ascii")
    fake_credential_store.set_password(SERVICE_NAME, account_id, initial_key_b64)

    payload = {"cookies": {"session": "abc123xyz"}}
    # write_credentials must readback first and reuse initial_key_b64
    store.write_credentials("reuse_prof", payload)

    # Key in store must NOT have been changed to a new key
    current_key_in_keystore = fake_credential_store.get_password(SERVICE_NAME, account_id)
    assert current_key_in_keystore == initial_key_b64

    # Credentials decrypt successfully
    assert store.read_credentials("reuse_prof") == payload


def test_deletion_intent_marker_distinguished_from_corruption(fake_credential_store):
    """A interrupted deletion leaves deletion marker; subsequent read cleans up without MissingKeyError."""
    store = CredentialStore()
    store.write_credentials("del_intent_prof", {"cookies": {"SID": "123"}})
    identity = get_installation_identity()
    account_id = f"{identity.installation_id}:del_intent_prof"

    enc_path = get_profile_dir("del_intent_prof") / "credentials.enc"
    assert enc_path.exists()

    # Simulate crash during delete after key is deleted but before credentials.enc is unlinked
    fake_credential_store.delete_password(SERVICE_NAME, account_id)
    store._write_operation_marker("del_intent_prof", operation="delete", phase="preparing")

    # read_credentials detects deletion intent, unlinks leftover ciphertext, and returns None cleanly
    assert store.read_credentials("del_intent_prof") is None
    assert not enc_path.exists()
    assert store._read_operation_marker("del_intent_prof") is None


def test_read_credentials_does_not_create_installation_json(tmp_path):
    """read_credentials is non-mutating and does not create installation.json if absent."""
    store = CredentialStore(storage_dir=tmp_path)
    assert store.read_credentials("nonexistent_prof") is None
    assert not (tmp_path / "installation.json").exists()


def test_backend_mismatch_blocks_mutation(fake_credential_store):
    """Recorded backend mismatch raises BackendMismatchError to prevent silent switching."""
    storage_dir = get_storage_dir()
    _ = get_installation_identity(storage_dir)

    install_file = storage_dir / "installation.json"
    data = json.loads(install_file.read_text(encoding="utf-8"))
    data["backend_id"] = "DifferentBackend.Keyring"
    install_file.write_text(json.dumps(data))

    with pytest.raises(BackendMismatchError):
        check_installation_identity(storage_dir)


def test_profile_exists_returns_true_for_credentials_enc_only_task3_routing_expectation():
    """profile_exists returns True when only credentials.enc exists; load_profile routes in Task 3."""
    from notebooklm_tools.core.exceptions import AuthenticationError
    from notebooklm_tools.services.auth import AuthManager

    prof_dir = get_profile_dir("only_enc_prof")
    prof_dir.mkdir(parents=True, exist_ok=True)
    (prof_dir / "credentials.enc").write_bytes(b"dummy_envelope")

    auth = AuthManager("only_enc_prof")
    assert auth.profile_exists() is True

    # Expectation: In file mode, load_profile() looks for cookies.json and raises AuthenticationError
    with pytest.raises(AuthenticationError):
        auth.load_profile()


def test_unavailable_keystore_surfaces_as_backend_unavailable_not_mismatch():
    """Locked or unavailable keystore raises BackendUnavailableError, not BackendMismatchError."""
    from notebooklm_tools.core.credential_backend_worker import CredentialWorkerClient
    from notebooklm_tools.core.credential_store import BackendUnavailableError

    storage_dir = get_storage_dir()
    install_file = storage_dir / "installation.json"
    install_file.write_text(
        json.dumps(
            {
                "version": 1,
                "installation_id": "test_install_id",
                "canonical_root": str(storage_dir.resolve()),
                "backend_id": "SecretService.Keyring",
            }
        ),
        encoding="utf-8",
    )

    class UnavailableWorker(CredentialWorkerClient):
        def __init__(self):
            pass

        def identify(self) -> str:
            raise BackendUnavailableError("D-Bus connection refused / keystore locked")

    worker = UnavailableWorker()
    with pytest.raises(BackendUnavailableError) as exc_info:
        check_installation_identity(storage_dir, worker=worker)

    assert "keystore locked" in str(exc_info.value) or "unavailable" in str(exc_info.value).lower()
    assert not isinstance(exc_info.value, BackendMismatchError)


def test_moved_root_allows_read_credentials_but_blocks_mutations(fake_credential_store):
    """Moved root permits non-mutating diagnostic reads, but strictly blocks writes and deletes."""
    storage_dir = get_storage_dir()
    store = CredentialStore(storage_dir=storage_dir)
    payload = {"cookies": {"SID": "valid_cookie"}, "csrf_token": "token123"}
    store.write_credentials("moved_root_prof", payload)

    # Tamper canonical root to simulate an unconfirmed root move
    install_file = storage_dir / "installation.json"
    data = json.loads(install_file.read_text(encoding="utf-8"))
    data["canonical_root"] = "/previous/moved/path"
    install_file.write_text(json.dumps(data), encoding="utf-8")

    # Non-mutating read MUST succeed!
    read_payload = store.read_credentials("moved_root_prof")
    assert read_payload == payload

    # Mutations MUST be strictly blocked
    with pytest.raises(InstallationPathMismatchError):
        store.write_credentials("moved_root_prof", {"cookies": {"SID": "new"}})

    with pytest.raises(InstallationPathMismatchError):
        store.delete_credentials("moved_root_prof")


def test_orphaned_write_preparing_marker_behavior(fake_credential_store):
    """An orphaned write/preparing marker does not block reading valid ciphertext, and subsequent write clears it."""
    store = CredentialStore()
    payload = {"cookies": {"SID": "orig_session"}}
    store.write_credentials("orphan_prof", payload)

    # Simulate crash during preparing phase of a later write
    store._write_operation_marker("orphan_prof", operation="write", phase="preparing")
    assert store._read_operation_marker("orphan_prof") is not None

    # Read succeeds and returns the valid committed ciphertext
    assert store.read_credentials("orphan_prof") == payload

    # Subsequent write successfully overwrites and clears the orphaned marker
    new_payload = {"cookies": {"SID": "updated_session"}}
    store.write_credentials("orphan_prof", new_payload)
    assert store.read_credentials("orphan_prof") == new_payload
    assert store._read_operation_marker("orphan_prof") is None

    # Fresh profile with no ciphertext and an orphaned write/preparing marker returns None
    store._write_operation_marker("empty_orphan_prof", operation="write", phase="preparing")
    assert store.read_credentials("empty_orphan_prof") is None


def test_installation_identity_file_is_never_visible_half_written(tmp_path, monkeypatch):
    """A reader outside the lock must never see installation.json before it is complete.

    The identity is written to a temporary file and renamed into place, so at every
    fsync during creation the final file must not exist yet.
    """
    inst_dir = tmp_path / "atomic_inst"
    install_file = inst_dir / "installation.json"
    seen_final_file_during_write = []
    real_fsync = os.fsync

    def spying_fsync(fd):
        seen_final_file_during_write.append(install_file.exists())
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", spying_fsync)

    identity = get_installation_identity(inst_dir)

    assert seen_final_file_during_write, "expected the identity to be fsynced while written"
    assert not any(seen_final_file_during_write)
    assert install_file.exists()
    assert json.loads(install_file.read_text())["installation_id"] == identity.installation_id
    assert not list(inst_dir.glob("installation.json.tmp*")), "temp file must not be left behind"
