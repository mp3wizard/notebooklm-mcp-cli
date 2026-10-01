"""Tests verifying test isolation and fail-closed guards for credential storage."""

import os
import subprocess
import sys
from pathlib import Path

import keyring
import pytest

from notebooklm_tools.core.credential_store import (
    MAX_KEYSTORE_ITEM_LENGTH,
    KeystoreItemTooLargeError,
    RealCredentialStoreAccessAttemptedError,
    get_backend,
)


def test_real_keystore_access_fails_closed_by_default():
    """Any access to credential backend in a normal test must fail closed."""
    backend = get_backend()
    with pytest.raises(RealCredentialStoreAccessAttemptedError):
        backend.get_password("notebooklm-mcp-cli.credentials.v1", "account1")

    with pytest.raises(RealCredentialStoreAccessAttemptedError):
        backend.set_password("notebooklm-mcp-cli.credentials.v1", "account1", "secret")

    with pytest.raises(RealCredentialStoreAccessAttemptedError):
        backend.delete_password("notebooklm-mcp-cli.credentials.v1", "account1")


def test_direct_keyring_access_fails_closed_by_default():
    """Direct access to keyring library in tests must also fail closed."""
    with pytest.raises(RealCredentialStoreAccessAttemptedError):
        keyring.get_password("notebooklm-mcp-cli.credentials.v1", "account1")

    with pytest.raises(RealCredentialStoreAccessAttemptedError):
        keyring.set_password("notebooklm-mcp-cli.credentials.v1", "account1", "secret")

    with pytest.raises(RealCredentialStoreAccessAttemptedError):
        keyring.delete_password("notebooklm-mcp-cli.credentials.v1", "account1")


def test_fake_credential_store_fixture(fake_credential_store):
    """The fake_credential_store fixture provides an isolated in-memory backend."""
    backend = get_backend()
    assert backend.get_password("service1", "acc1") is None

    backend.set_password("service1", "acc1", "val1")
    assert backend.get_password("service1", "acc1") == "val1"

    backend.delete_password("service1", "acc1")
    assert backend.get_password("service1", "acc1") is None


def test_keystore_item_length_limit(fake_credential_store):
    """Stored items in the OS keystore must never exceed 1,000 characters.

    Windows Credential Manager fails above ~1,280 characters. Our contract
    requires storing ONLY the 44-character 256-bit base64 key, and strictly
    rejecting any item larger than 1,000 characters.
    """
    backend = get_backend()

    # 44-character base64 key (standard encryption key size)
    key_44 = "A" * 44
    backend.set_password("service", "key44", key_44)
    assert backend.get_password("service", "key44") == key_44

    # 1,000 characters is the maximum allowed
    key_1000 = "B" * MAX_KEYSTORE_ITEM_LENGTH
    backend.set_password("service", "key1000", key_1000)
    assert backend.get_password("service", "key1000") == key_1000

    # > 1,000 characters must fail closed
    oversize_payload = "C" * (MAX_KEYSTORE_ITEM_LENGTH + 1)
    with pytest.raises(KeystoreItemTooLargeError):
        backend.set_password("service", "too_large", oversize_payload)

    # 1,280 and 1,300 characters (payload size) must fail
    with pytest.raises(KeystoreItemTooLargeError):
        backend.set_password("service", "full_cookies_json", "D" * 1280)


def test_storage_isolated_from_operator_directory(tmp_path):
    """Normal tests must run in isolated temporary storage, never touching real home."""
    storage_env = os.environ.get("NOTEBOOKLM_MCP_CLI_PATH")
    assert storage_env is not None
    assert str(Path.home() / ".notebooklm-mcp-cli") != storage_env
    assert str(tmp_path) in storage_env


def test_detect_os_backend_fails_closed():
    """Calling _detect_os_backend in a test must raise RealCredentialStoreAccessAttemptedError."""
    from notebooklm_tools.core.credential_store import _detect_os_backend

    with pytest.raises(RealCredentialStoreAccessAttemptedError):
        _detect_os_backend()


def test_set_backend_factory_none_still_fails_closed():
    """Setting backend factory to None inside a test must still fail closed and not reach real store."""
    from notebooklm_tools.core.credential_store import set_backend_factory

    set_backend_factory(None)
    with pytest.raises(RealCredentialStoreAccessAttemptedError):
        get_backend().get_password("notebooklm-mcp-cli.credentials.v1", "account1")


def test_subprocess_credential_store_access_fails_closed():
    """Subprocess running with test launcher must fail closed if accessing credential store."""
    launcher = Path(__file__).parent / "test_launcher.py"
    code = "from notebooklm_tools.core.credential_store import get_backend; get_backend().get_password('s', 'a')"
    res = subprocess.run(
        [sys.executable, str(launcher), "-c", code],
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0
    assert "RealCredentialStoreAccessAttemptedError" in res.stderr


def test_subprocess_direct_keyring_access_fails_closed():
    """Subprocess running with test launcher must fail closed if accessing keyring directly."""
    launcher = Path(__file__).parent / "test_launcher.py"
    code = "import keyring; keyring.get_password('s', 'a')"
    res = subprocess.run(
        [sys.executable, str(launcher), "-c", code],
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0
    assert "RealCredentialStoreAccessAttemptedError" in res.stderr


def test_e2e_isolation_forces_file_mode():
    """E2E runs and defaults must resolve to file mode to guarantee no migration/deletion."""
    from notebooklm_tools.utils.config import get_auth_storage_mode

    assert get_auth_storage_mode("default") == "file"
