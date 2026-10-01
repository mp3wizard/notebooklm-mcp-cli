#!/usr/bin/env python3
"""Cross-platform smoke test script for Protected mode credential storage.

Tests the OS credential store integration end-to-end on macOS, Linux, and Windows:
1. set protected -> status -> read -> no plaintext left -> set file -> old layout back
2. 90 KB payload (large cookie jar)
3. Two processes doing read/replace at once (concurrency & locking)
4. Locked/unavailable path giving the plain error
5. Cleanup of keychain item, verified

Safety guarantees:
- Always uses a unique test service name (passed via --service-name or auto-generated).
- Always uses a temporary directory for storage (never touches ~/.notebooklm-mcp-cli).
- Never modifies HOME on macOS (prevents Keychain popup/corruption).
- Uses synthetic dummy data only (no real Google accounts or network calls).
- Cleans up and verifies deletion of all keystore items created during the test.

Usage:
    python scripts/smoke_credential_store.py [--service-name <name>] [--pause]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Ensure src/ is on sys.path if running directly from repository checkout
_REPO_SRC = Path(__file__).resolve().parent.parent / "src"
if _REPO_SRC.exists() and str(_REPO_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO_SRC))


def log_step(name: str) -> None:
    print(f"\n=== Step: {name} ===")


def log_pass(msg: str) -> None:
    print(f"  [PASS] {msg}")


def log_fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def check_macos_home_safety() -> None:
    """Refuse to run on macOS if HOME was pointed at a temporary directory."""
    if sys.platform == "darwin":
        import pwd

        real_home = pwd.getpwuid(os.getuid()).pw_dir
        current_home = os.environ.get("HOME")
        if current_home and os.path.realpath(current_home) != os.path.realpath(real_home):
            sys.stderr.write(
                f"ERROR: HOME is set to '{current_home}', but real user home is '{real_home}'.\n"
                "On macOS, changing HOME breaks login keychain access and can trigger system dialogs.\n"
                "Do not modify HOME; isolate tests with NOTEBOOKLM_MCP_CLI_PATH and a unique service name instead.\n"
            )
            sys.exit(1)


def run_worker_subcommand(args: list[str]) -> None:
    """Helper subcommands executed in child processes."""
    if "--worker-replace" in args:
        # Args: --worker-replace <profile_name> <marker_value> <storage_dir> <service_name>
        idx = args.index("--worker-replace")
        profile_name = args[idx + 1]
        marker_value = args[idx + 2]
        storage_dir = Path(args[idx + 3])
        service_name = args[idx + 4]

        os.environ["NOTEBOOKLM_MCP_CLI_PATH"] = str(storage_dir)
        os.environ["NOTEBOOKLM_KEYSTORE_SERVICE_NAME"] = service_name
        os.environ["ALLOW_REAL_KEYSTORE"] = "1"

        from notebooklm_tools.core.auth import AuthManager

        # Short sleep to increase chance of concurrent collision
        time.sleep(0.05)
        auth = AuthManager(profile_name)
        current = auth.load_profile(force_reload=True)
        updated_cookies = dict(current.cookies)
        updated_cookies["worker_marker"] = marker_value
        updated_cookies["worker_time"] = str(time.time())
        auth.save_profile(
            cookies=updated_cookies,
            csrf_token=f"csrf_{marker_value}",
            email=f"{marker_value}@example.com",
            force=True,
        )
        sys.exit(0)


def step1_lifecycle(temp_dir: Path, service_name: str) -> bool:
    """Test full storage mode switch lifecycle and plaintext elimination."""
    log_step("1. Storage Mode Lifecycle (file -> protected -> read -> file)")
    profile_name = "smoke_prof_1"

    from notebooklm_tools.core.auth import AuthManager
    from notebooklm_tools.services.auth_storage import get_storage_status, set_storage_mode

    # 1. Create profile in file mode with dummy data
    auth = AuthManager(profile_name)
    initial_cookies = {"SID": "dummy_sid_123", "HSID": "dummy_hsid_456"}
    auth.save_profile(
        cookies=initial_cookies,
        csrf_token="dummy_csrf_token_abc",
        session_id="dummy_session_id_xyz",
        email="smoke1@example.com",
        force=True,
    )

    profile_dir = temp_dir / "profiles" / profile_name
    cookies_path = profile_dir / "cookies.json"
    auth_path = profile_dir / "auth.json"
    enc_path = profile_dir / "credentials.enc"

    if not cookies_path.exists():
        log_fail("cookies.json was not created in file mode")
        return False
    log_pass("Profile created in file mode with plaintext cookies.json")

    # 2. Switch to protected mode
    res = set_storage_mode("protected", profile_name=profile_name)
    if res.get("status") not in ("updated", "unchanged") or res.get("mode") != "protected":
        log_fail(f"set_storage_mode('protected') returned failure: {res}")
        return False

    status = get_storage_status(profile_name=profile_name)
    if (
        status.get("mode") != "protected"
        or not status.get("has_ciphertext")
        or status.get("has_legacy")
    ):
        log_fail(f"Status does not reflect protected mode: {status}")
        return False
    log_pass("Storage mode set to protected; status verified")

    # 3. Read back credentials and verify decryption
    loaded = auth.load_profile(force_reload=True)
    if loaded.cookies != initial_cookies:
        log_fail(f"Decrypted cookies mismatch: got {loaded.cookies}, expected {initial_cookies}")
        return False
    if loaded.csrf_token != "dummy_csrf_token_abc":
        log_fail(f"Decrypted csrf_token mismatch: got {loaded.csrf_token}")
        return False
    log_pass("Credentials read and decrypted successfully from credentials.enc")

    # 4. Verify no plaintext secrets left on disk
    if cookies_path.exists():
        log_fail("Plaintext cookies.json still exists after migration to protected mode!")
        return False

    if auth_path.exists():
        auth_data = json.loads(auth_path.read_text(encoding="utf-8"))
        for secret_key in ("cookies", "csrf_token", "session_id"):
            if secret_key in auth_data:
                log_fail(f"Secret key '{secret_key}' found in plaintext auth.json!")
                return False

    root_auth = temp_dir / "auth.json"
    if root_auth.exists():
        root_data = json.loads(root_auth.read_text(encoding="utf-8"))
        for secret_key in ("cookies", "csrf_token", "session_id"):
            if secret_key in root_data:
                log_fail(f"Secret key '{secret_key}' found in root auth.json!")
                return False
    log_pass("No plaintext credentials left on disk (cookies.json deleted, metadata sanitized)")

    # 5. Switch back to file mode (export)
    res_file = set_storage_mode("file", profile_name=profile_name)
    if res_file.get("status") not in ("updated", "unchanged") or res_file.get("mode") != "file":
        log_fail(f"set_storage_mode('file') returned failure: {res_file}")
        return False

    status_file = get_storage_status(profile_name=profile_name)
    if (
        status_file.get("mode") != "file"
        or status_file.get("has_ciphertext")
        or not status_file.get("has_legacy")
    ):
        log_fail(f"Status does not reflect file mode: {status_file}")
        return False

    if not cookies_path.exists():
        log_fail("cookies.json was not restored in file mode")
        return False

    if enc_path.exists():
        log_fail("credentials.enc was not removed after switching back to file mode")
        return False

    # Check file permissions on POSIX
    if os.name == "posix":
        mode = cookies_path.stat().st_mode & 0o777
        if mode != 0o600:
            log_fail(f"cookies.json permissions are {oct(mode)}, expected 0600")
            return False

    loaded_file = auth.load_profile(force_reload=True)
    if loaded_file.cookies != initial_cookies:
        log_fail("Restored file mode cookies mismatch")
        return False

    log_pass("Switched back to file mode: old layout restored, permissions 0600 verified")
    return True


def step2_large_payload(temp_dir: Path, service_name: str) -> bool:
    """Test storing and retrieving a large 90 KB credential payload."""
    log_step("2. Large Credential Payload (90 KB)")
    profile_name = "smoke_prof_large"

    from notebooklm_tools.core.auth import AuthManager
    from notebooklm_tools.services.auth_storage import set_storage_mode

    auth = AuthManager(profile_name)
    # Generate ~90 KB of cookie data
    large_cookies = {f"COOKIE_{i:04d}": "V" * 80 for i in range(1000)}
    auth.save_profile(
        cookies=large_cookies,
        csrf_token="csrf_large_payload",
        email="large@example.com",
        force=True,
    )

    res = set_storage_mode("protected", profile_name=profile_name)
    if res.get("status") not in ("updated", "unchanged") or res.get("mode") != "protected":
        log_fail(f"set_storage_mode('protected') returned failure: {res}")
        return False

    enc_path = temp_dir / "profiles" / profile_name / "credentials.enc"
    if not enc_path.exists():
        log_fail("credentials.enc not created for large payload")
        return False

    enc_size = enc_path.stat().st_size
    if enc_size < 85 * 1024:
        log_fail(f"Ciphertext size is only {enc_size} bytes, expected > 85 KB")
        return False

    loaded = auth.load_profile(force_reload=True)
    if loaded.cookies != large_cookies:
        log_fail("Decrypted 90 KB payload does not match original data!")
        return False

    log_pass(
        f"Successfully encrypted and decrypted {enc_size} bytes ({len(large_cookies)} cookies)"
    )
    return True


def step3_concurrent_processes(temp_dir: Path, service_name: str) -> bool:
    """Test two concurrent processes reading and replacing credentials in protected mode."""
    log_step("3. Concurrent Read/Replace (Two Processes)")
    profile_name = "smoke_prof_race"

    from notebooklm_tools.core.auth import AuthManager
    from notebooklm_tools.services.auth_storage import set_storage_mode

    # Setup profile in protected mode
    auth = AuthManager(profile_name)
    auth.save_profile(
        cookies={"init": "val0"},
        csrf_token="token0",
        email="race@example.com",
        force=True,
    )
    set_storage_mode("protected", profile_name=profile_name)

    # Spawn 2 worker processes
    env = os.environ.copy()
    p1 = subprocess.Popen(
        [
            sys.executable,
            __file__,
            "--worker-replace",
            profile_name,
            "PROC_1",
            str(temp_dir),
            service_name,
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    p2 = subprocess.Popen(
        [
            sys.executable,
            __file__,
            "--worker-replace",
            profile_name,
            "PROC_2",
            str(temp_dir),
            service_name,
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    out1, err1 = p1.communicate(timeout=30)
    out2, err2 = p2.communicate(timeout=30)

    if p1.returncode != 0:
        log_fail(f"Process 1 failed with code {p1.returncode}: {err1}")
        return False
    if p2.returncode != 0:
        log_fail(f"Process 2 failed with code {p2.returncode}: {err2}")
        return False

    # Verify ciphertext integrity
    loaded = auth.load_profile(force_reload=True)
    marker = loaded.cookies.get("worker_marker")
    if marker not in ("PROC_1", "PROC_2"):
        log_fail(f"Corrupted or unexpected worker marker in cookies: {loaded.cookies}")
        return False

    log_pass(
        f"Concurrent execution succeeded cleanly (final state from {marker}, ciphertext intact)"
    )
    return True


def step4_unavailable_handling(temp_dir: Path, service_name: str) -> bool:
    """Test handling and clean refusal when OS keystore is unavailable/locked."""
    log_step("4. Locked / Unavailable Keystore Refusal")
    profile_name = "smoke_prof_unavail"

    from notebooklm_tools.core.auth import AuthManager
    from notebooklm_tools.core.credential_store import (
        BackendUnavailableError,
        CredentialStore,
        set_backend_factory,
    )
    from notebooklm_tools.services.auth_storage import get_storage_status, set_storage_mode
    from notebooklm_tools.services.errors import ServiceError

    auth = AuthManager(profile_name)
    initial_cookies = {"SID": "persist_sid"}
    auth.save_profile(
        cookies=initial_cookies,
        csrf_token="persist_csrf",
        email="unavail@example.com",
        force=True,
    )

    # Check whether real keystore is currently available
    real_store = CredentialStore(storage_dir=temp_dir, service_name=service_name)
    keystore_available = real_store.is_available()

    if not keystore_available:
        # We are on a headless Linux or Windows SSH session where keystore is genuinely unavailable
        print("  [INFO] Keystore is genuinely unavailable in this session (e.g. headless/SSH)")
        try:
            set_storage_mode("protected", profile_name=profile_name)
            log_fail("set_storage_mode succeeded when keystore is unavailable!")
            return False
        except ServiceError as exc:
            msg = getattr(exc, "user_message", str(exc))
            if (
                "unavailable or locked" not in msg.lower()
                and "locked or unavailable" not in msg.lower()
            ):
                log_fail(f"Unexpected error message: {msg}")
                return False
            log_pass(f"Refused with clear error: {msg}")
    else:
        # Keystore is available on desktop; test refusal code path with UnavailableBackend
        print("  [INFO] Keystore is available; testing refusal with simulated unavailable backend")

        class UnavailableBackend:
            def identify(self) -> str:
                raise BackendUnavailableError("OS credential store is unavailable or locked.")

            def get_password(self, service: str, account: str) -> str | None:
                raise BackendUnavailableError("OS credential store is unavailable or locked.")

            def set_password(self, service: str, account: str, password: str) -> None:
                raise BackendUnavailableError("OS credential store is unavailable or locked.")

            def delete_password(self, service: str, account: str) -> None:
                raise BackendUnavailableError("OS credential store is unavailable or locked.")

        set_backend_factory(UnavailableBackend)
        try:
            set_storage_mode("protected", profile_name=profile_name)
            log_fail("set_storage_mode succeeded when backend is unavailable!")
            return False
        except ServiceError as exc:
            msg = getattr(exc, "user_message", str(exc))
            if (
                "unavailable or locked" not in msg.lower()
                and "locked or unavailable" not in msg.lower()
            ):
                log_fail(f"Unexpected error message: {msg}")
                return False
            log_pass(f"Refused with clear error: {msg}")
        finally:
            set_backend_factory(None)

    # Confirm original profile in file mode was untouched
    status = get_storage_status(profile_name=profile_name)
    if status.get("mode") != "file" or not status.get("has_legacy") or status.get("has_ciphertext"):
        log_fail(f"Profile state altered during failed migration: {status}")
        return False

    loaded = auth.load_profile(force_reload=True)
    if loaded.cookies.get("SID") != "persist_sid":
        log_fail("Original cookies corrupted during failed migration attempt")
        return False

    log_pass("Profile remained safely in file mode and all credentials preserved")
    return True


def step5_cleanup(temp_dir: Path, service_name: str, silent: bool = False) -> bool:
    """Verify complete cleanup of all keystore items created during tests."""
    if not silent:
        log_step("5. Keystore Item Cleanup & Verification")

    from notebooklm_tools.core.credential_store import (
        CredentialStore,
        get_installation_identity,
    )

    install_id = get_installation_identity(temp_dir).installation_id
    store = CredentialStore(storage_dir=temp_dir, service_name=service_name)

    profiles_to_clean = [
        "smoke_prof_1",
        "smoke_prof_large",
        "smoke_prof_race",
        "smoke_prof_unavail",
    ]
    for prof in profiles_to_clean:
        account = f"{install_id}:{prof}"
        with contextlib.suppress(Exception):
            store.delete_credentials(prof)
        with contextlib.suppress(Exception):
            store._worker.delete_password(service_name, account)

        # Verify deletion
        val = store._worker.get_password(service_name, account)
        if val is not None:
            if not silent:
                log_fail(f"Keystore item '{account}' under '{service_name}' was not deleted!")
            return False

    # Platform-specific extra verification
    if sys.platform == "darwin":
        # Check security find-generic-password returns non-zero
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", service_name],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            if not silent:
                log_fail(f"macOS Keychain still contains items for service '{service_name}'")
            return False

    if not silent:
        log_pass(f"All keystore items for test service '{service_name}' verified deleted")
    return True


def main() -> int:
    check_macos_home_safety()

    # First handle internal worker calls
    run_worker_subcommand(sys.argv)

    parser = argparse.ArgumentParser(description="Cross-platform smoke tests for Protected mode.")
    parser.add_argument(
        "--service-name",
        default=f"test.nlm.smoke.{secrets.token_hex(4)}",
        help="Unique OS keystore service name for testing",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Do not delete temporary storage directory upon completion",
    )
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Pause for user input before exiting (for Windows double-click)",
    )
    args = parser.parse_args()

    print("================================================================")
    print("NotebookLM Protected Mode - Cross-Platform Smoke Tests")
    print(f"Platform: {sys.platform} (Python {sys.version.split()[0]})")
    print(f"Test Service Name: {args.service_name}")
    print("================================================================")

    temp_storage = tempfile.mkdtemp(prefix="nlm_smoke_")
    temp_dir = Path(temp_storage)

    # Export mandatory isolation environment variables
    # (NOTE: HOME is NEVER modified here or anywhere in tests!)
    os.environ["NOTEBOOKLM_MCP_CLI_PATH"] = str(temp_dir)
    os.environ["NOTEBOOKLM_KEYSTORE_SERVICE_NAME"] = args.service_name
    os.environ["ALLOW_REAL_KEYSTORE"] = "1"

    from notebooklm_tools.utils.config import reset_config

    reset_config()

    refusal_only = False
    all_passed = True
    try:
        from notebooklm_tools.core.credential_store import CredentialStore

        preflight_store = CredentialStore(storage_dir=temp_dir, service_name=args.service_name)
        if not preflight_store.is_available():
            refusal_only = True
            print(
                "\n[INFO] Real keystore is unavailable in this environment (headless/SSH session)."
            )
            print("Steps 1-3 are marked [SKIPPED]; testing Step 4 refusal path.")
            print("  [SKIPPED] Step 1: Migration lifecycle & secret persistence")
            print("  [SKIPPED] Step 2: Large payload preservation")
            print("  [SKIPPED] Step 3: Concurrent process safety")
            if not step4_unavailable_handling(temp_dir, args.service_name):
                all_passed = False
            # The keystore can't be reached here, so nothing was written to it.
            print("  [SKIPPED] Step 5: Keystore cleanup (keystore unavailable, nothing written)")
        else:
            if not step1_lifecycle(temp_dir, args.service_name):
                all_passed = False
            if not step2_large_payload(temp_dir, args.service_name):
                all_passed = False
            if not step3_concurrent_processes(temp_dir, args.service_name):
                all_passed = False
            if not step4_unavailable_handling(temp_dir, args.service_name):
                all_passed = False
            if not step5_cleanup(temp_dir, args.service_name):
                all_passed = False
    except Exception as exc:
        log_fail(f"Unhandled exception during smoke tests: {exc}")
        import traceback

        traceback.print_exc()
        all_passed = False
    finally:
        # Final cleanup attempt
        if not refusal_only:
            with contextlib.suppress(Exception):
                step5_cleanup(temp_dir, args.service_name, silent=True)

        if not args.keep_temp:
            shutil.rmtree(temp_storage, ignore_errors=True)
            print(f"\nCleaned up temporary storage directory: {temp_storage}")
        else:
            print(f"\nPreserved temporary storage directory: {temp_storage}")

    print("\n================================================================")
    if all_passed:
        if refusal_only:
            print("RESULT: PASS (refusal path only)")
        else:
            print("RESULT: ALL 5 SMOKE TESTS PASSED [OK]")
    else:
        print("RESULT: SMOKE TESTS FAILED [FAIL]")
    print("================================================================")

    if args.pause or not sys.stdin.isatty():
        with contextlib.suppress(Exception):
            input("\nPress Enter to exit...")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
