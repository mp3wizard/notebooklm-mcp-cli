"""Tests for credential backend helper worker process and bounded execution."""

import os

import pytest

from notebooklm_tools.core.credential_backend_worker import (
    BackendTimeoutError,
    CredentialWorkerClient,
    is_desktop_session,
)
from notebooklm_tools.core.credential_store import (
    InMemoryCredentialBackend,
    RealCredentialStoreAccessAttemptedError,
)


def test_desktop_session_detection():
    """is_desktop_session returns a boolean."""
    assert isinstance(is_desktop_session(), bool)


def test_worker_in_memory_backend():
    """Worker client works with an in-memory backend directly."""
    backend = InMemoryCredentialBackend()
    worker = CredentialWorkerClient(backend=backend)

    assert worker.get_password("test_srv", "acc1") is None
    worker.set_password("test_srv", "acc1", "secret_val")
    assert worker.get_password("test_srv", "acc1") == "secret_val"

    worker.delete_password("test_srv", "acc1")
    assert worker.get_password("test_srv", "acc1") is None


def test_in_process_timeout_does_not_block_caller():
    """In-process timeout terminates immediately without waiting for hung thread."""
    import time

    class HangingBackend:
        def get_password(self, service: str, account: str) -> str | None:
            time.sleep(5)
            return "too_late"

        def set_password(self, service: str, account: str, password: str) -> None:
            time.sleep(5)

        def delete_password(self, service: str, account: str) -> None:
            time.sleep(5)

    worker = CredentialWorkerClient(backend=HangingBackend(), timeout_seconds=0.1)
    t0 = time.monotonic()
    with pytest.raises(BackendTimeoutError) as exc_info:
        worker.get_password("test_srv", "acc1")

    elapsed = time.monotonic() - t0
    assert elapsed < 1.0  # Caller regains control promptly, not waiting 5s!
    err = str(exc_info.value)
    assert "timed out" in err.lower()


def test_worker_timeout_regains_control_promptly_and_reaps():
    """Helper subprocess times out, caller regains control in < 2.0s, and helper PID is reaped."""
    import sys
    import time

    # Subprocess runs a Python command that reads stdin then sleeps 10s
    worker = CredentialWorkerClient(
        backend=None,
        use_subprocess=True,
        timeout_seconds=0.5,
        helper_cmd=[sys.executable, "-c", "import sys, time; sys.stdin.readline(); time.sleep(10)"],
    )

    t0 = time.monotonic()
    with pytest.raises(BackendTimeoutError):
        worker.get_password("test_srv", "acc1")

    elapsed = time.monotonic() - t0
    # Must regain control in < 2.0s
    assert elapsed < 2.0

    # Helper process must be reaped and terminated
    proc = worker._last_helper_proc
    assert proc is not None
    assert proc.poll() is not None  # Process has exited and returncode is available

    # Check that the process PID no longer survives
    if hasattr(os, "kill"):
        import contextlib

        with contextlib.suppress(ProcessLookupError):
            os.kill(proc.pid, 0)


def test_worker_helper_fails_closed_in_tests():
    """Worker helper process started in tests must fail closed against real store."""
    worker = CredentialWorkerClient(backend=None, use_subprocess=True, timeout_seconds=2.0)
    with pytest.raises((RealCredentialStoreAccessAttemptedError, RuntimeError)):
        worker.get_password("test_srv", "acc1")


def test_credential_store_production_wiring(tmp_path):
    """CredentialStore() in production wiring uses subprocess and has no in-process backend."""
    from notebooklm_tools.core.credential_store import (
        CredentialStore,
        get_backend_factory,
        set_backend_factory,
    )

    old_factory = get_backend_factory()
    set_backend_factory(None)
    try:
        store = CredentialStore(storage_dir=tmp_path)
        assert store._worker._use_subprocess is True
        assert store._worker._backend is None
    finally:
        set_backend_factory(old_factory)


def test_credential_store_subprocess_roundtrip_with_test_launcher(tmp_path):
    """CredentialStore works through a helper subprocess via private stdin/stdout pipes."""
    import sys

    from notebooklm_tools.core.credential_store import (
        CredentialStore,
        get_backend_factory,
        set_backend_factory,
    )

    db_file = tmp_path / "fake_keystore.json"
    helper_script = tmp_path / "fake_worker.py"
    helper_script.write_text(
        f"""
import sys, json, os

db_path = {str(db_file)!r}
store = {{}}
if os.path.exists(db_path):
    with open(db_path, "r", encoding="utf-8") as f:
        store = json.load(f)

for line in sys.stdin:
    if not line.strip():
        break
    req = json.loads(line)
    op = req.get("op")
    srv = req.get("service")
    acc = req.get("account")
    key = str(srv) + ":" + str(acc)
    if op == "identify":
        sys.stdout.write(json.dumps({{"ok": True, "result": "fake_test_backend"}}) + "\\n")
    elif op == "get":
        sys.stdout.write(json.dumps({{"ok": True, "result": store.get(key)}}) + "\\n")
    elif op == "set":
        store[key] = req.get("password")
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(store, f)
        sys.stdout.write(json.dumps({{"ok": True, "result": None}}) + "\\n")
    elif op == "delete":
        store.pop(key, None)
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(store, f)
        sys.stdout.write(json.dumps({{"ok": True, "result": None}}) + "\\n")
    elif op == "ensure_key":
        existing = store.get(key)
        if existing is not None:
            sys.stdout.write(json.dumps({{"ok": True, "result": {{"key": existing, "created": False, "backend_id": "fake_test_backend"}}}}) + "\\n")
        elif not req.get("allow_create", True):
            sys.stdout.write(json.dumps({{"ok": False, "error_type": "MissingKeyError", "error": "Missing key"}}) + "\\n")
        else:
            cand = req.get("candidate_key")
            store[key] = cand
            with open(db_path, "w", encoding="utf-8") as f:
                json.dump(store, f)
            sys.stdout.write(json.dumps({{"ok": True, "result": {{"key": cand, "created": True, "backend_id": "fake_test_backend"}}}}) + "\\n")
    sys.stdout.flush()
""",
        encoding="utf-8",
    )

    old_factory = get_backend_factory()
    set_backend_factory(None)
    try:
        store = CredentialStore(
            storage_dir=tmp_path,
            helper_cmd=[sys.executable, str(helper_script)],
        )
        assert store._worker._use_subprocess is True
        assert store._worker._backend is None

        payload = {"cookies": {"SID": "secret_session"}, "csrf_token": "csrf123"}
        store.write_credentials("subproc_profile", payload)

        loaded = store.read_credentials("subproc_profile")
        assert loaded == payload

        store.delete_credentials("subproc_profile")
        assert store.read_credentials("subproc_profile") is None
    finally:
        set_backend_factory(old_factory)
