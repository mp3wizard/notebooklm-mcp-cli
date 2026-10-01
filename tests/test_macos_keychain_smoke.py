"""Synthetic macOS Keychain smoke test.

Exercised only when ALLOW_REAL_KEYSTORE=1 is set on macOS.
Uses a randomized unique service ID and account ID, exercises the real helper subprocess path,
performs a bounded timeout check, and guarantees cleanup in a finally block.
"""

import os
import secrets
import sys
import time

import pytest

from notebooklm_tools.core.credential_backend_worker import (
    BackendTimeoutError,
    CredentialWorkerClient,
)


@pytest.mark.real_os_store
def test_macos_keychain_smoke_real_helper():
    """Verify real macOS Keychain access through helper subprocess with guaranteed cleanup."""
    if sys.platform != "darwin":
        pytest.skip("macOS Keychain smoke test only runs on macOS")

    if not os.environ.get("ALLOW_REAL_KEYSTORE"):
        pytest.skip("Set ALLOW_REAL_KEYSTORE=1 to run real OS keystore smoke tests")

    # Generate isolated random service and account IDs
    unique_suffix = secrets.token_hex(8)
    service_id = f"notebooklm.smoke.test.{unique_suffix}"
    account_id = f"account_{unique_suffix}"
    test_secret = secrets.token_hex(32)

    # Use the real production helper subprocess (backend=None, use_subprocess=True)
    worker = CredentialWorkerClient(backend=None, use_subprocess=True, timeout_seconds=15.0)

    try:
        # Step 1: Initial read on nonexistent item must return None
        initial = worker.get_password(service_id, account_id)
        assert initial is None, f"Expected None for new test item, got {initial!r}"

        # Step 2: Store secret in macOS Keychain
        worker.set_password(service_id, account_id, test_secret)

        # Step 3: Read back secret and verify exact match
        readback = worker.get_password(service_id, account_id)
        assert readback == test_secret, f"Secret mismatch: wrote {test_secret!r}, read {readback!r}"

        # Step 4: Verify timeout bounded execution (< 2.0s for 0.5s timeout)
        hanging_worker = CredentialWorkerClient(
            backend=None,
            use_subprocess=True,
            timeout_seconds=0.5,
            helper_cmd=[
                sys.executable,
                "-c",
                "import sys, time; sys.stdin.readline(); time.sleep(10)",
            ],
        )
        t0 = time.monotonic()
        with pytest.raises(BackendTimeoutError):
            hanging_worker.get_password(service_id, account_id)
        elapsed = time.monotonic() - t0
        assert elapsed < 2.0, f"Expected timeout < 2.0s, elapsed {elapsed:.2f}s"
        assert hanging_worker._last_helper_proc is not None
        assert hanging_worker._last_helper_proc.poll() is not None

    finally:
        # Step 5: Guaranteed cleanup
        import contextlib

        with contextlib.suppress(Exception):
            worker.delete_password(service_id, account_id)

        # Verify item is truly gone from Keychain
        with contextlib.suppress(Exception):
            assert worker.get_password(service_id, account_id) is None
