"""Cross-process-safe headless recovery does not relaunch a second browser."""

from __future__ import annotations

import multiprocessing
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from filelock import FileLock

from notebooklm_tools.core.exceptions import AuthenticationError
from notebooklm_tools.utils import cdp


def test_recovery_reuses_fresher_validated_credentials(tmp_path, monkeypatch):
    token = SimpleNamespace(revision="new", extracted_at=2, cookies={"SID": "new"})
    old = SimpleNamespace(revision="old", extracted_at=1)
    calls = iter([old, token])
    launch = Mock()
    monkeypatch.setattr("notebooklm_tools.core.auth.load_cached_tokens", lambda **_: next(calls))
    monkeypatch.setattr("notebooklm_tools.utils.config.get_storage_dir", lambda: tmp_path)
    monkeypatch.setattr(cdp, "_validate_headless_candidate", lambda *args: True)
    monkeypatch.setattr(cdp, "_run_headless_auth_unlocked", launch)

    assert cdp.run_headless_auth(profile_name="work", expected_revision="old") is token
    launch.assert_not_called()


def test_recovery_tries_browser_when_changed_credentials_are_rejected(tmp_path, monkeypatch):
    token = SimpleNamespace(revision="new", extracted_at=2, cookies={"SID": "new"})
    calls = iter([SimpleNamespace(revision="old", extracted_at=1), token])
    monkeypatch.setattr("notebooklm_tools.core.auth.load_cached_tokens", lambda **_: next(calls))
    monkeypatch.setattr("notebooklm_tools.utils.config.get_storage_dir", lambda: tmp_path)
    monkeypatch.setattr(cdp, "_validate_headless_candidate", lambda *args: False)
    launch = Mock(return_value="launched")
    monkeypatch.setattr(cdp, "_run_headless_auth_unlocked", launch)

    assert cdp.run_headless_auth(profile_name="work") == "launched"
    assert launch.call_count == 1


def test_two_threads_share_one_profile_recovery(tmp_path, monkeypatch):
    enter = threading.Event()
    release = threading.Event()
    renewed = SimpleNamespace(revision="new", extracted_at=4, cookies={"SID": "valid"})
    state = {"value": SimpleNamespace(revision="old", extracted_at=1)}
    attempts = []

    monkeypatch.setattr("notebooklm_tools.core.auth.load_cached_tokens", lambda **_: state["value"])
    monkeypatch.setattr("notebooklm_tools.utils.config.get_storage_dir", lambda: tmp_path)
    monkeypatch.setattr(cdp, "_validate_headless_candidate", lambda *args: True)

    def launch(**kwargs):
        attempts.append(kwargs["profile_name"])
        enter.set()
        assert release.wait(5)
        state["value"] = renewed
        return renewed

    monkeypatch.setattr(cdp, "_run_headless_auth_unlocked", launch)
    results = []
    worker1 = threading.Thread(
        target=lambda: results.append(cdp.run_headless_auth(profile_name="work"))
    )
    worker2 = threading.Thread(
        target=lambda: results.append(cdp.run_headless_auth(profile_name="work"))
    )
    worker1.start()
    assert enter.wait(5)
    worker2.start()
    release.set()
    worker1.join(6)
    worker2.join(6)
    assert not worker1.is_alive() and not worker2.is_alive()
    assert results == [renewed, renewed]
    assert attempts == ["work"]


def test_recovery_locks_distinct_profiles_independently(tmp_path, monkeypatch):
    monkeypatch.setattr("notebooklm_tools.core.auth.load_cached_tokens", lambda **_: None)
    monkeypatch.setattr("notebooklm_tools.utils.config.get_storage_dir", lambda: tmp_path)
    calls = []
    monkeypatch.setattr(
        cdp,
        "_run_headless_auth_unlocked",
        lambda **kwargs: calls.append(kwargs["profile_name"]) or True,
    )
    assert cdp.run_headless_auth(profile_name="a") is True
    assert cdp.run_headless_auth(profile_name="b") is True
    assert calls == ["a", "b"]


def _hold_recovery_lock(lock_path: str, started, release):
    with FileLock(Path(lock_path), timeout=5):
        started.set()
        release.wait(8)


def test_concurrent_process_cannot_launch_second_browser(tmp_path, monkeypatch):
    """An independent process holds the lock, so the contender fails safely."""
    ctx = multiprocessing.get_context("spawn")
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir()
    started, release = ctx.Event(), ctx.Event()
    holder = ctx.Process(
        target=_hold_recovery_lock,
        args=(str(lock_dir / "work.recovery.lock"), started, release),
    )
    holder.start()
    try:
        assert started.wait(8)
        monkeypatch.setattr("notebooklm_tools.core.auth.load_cached_tokens", lambda **_: None)
        monkeypatch.setattr("notebooklm_tools.utils.config.get_storage_dir", lambda: tmp_path)
        launch = Mock(side_effect=AssertionError("must not start another browser"))
        monkeypatch.setattr(cdp, "_run_headless_auth_unlocked", launch)
        with pytest.raises(AuthenticationError, match="already running"):
            cdp.run_headless_auth(profile_name="work", timeout=1, raise_on_error=True)
        launch.assert_not_called()
    finally:
        release.set()
        holder.join(10)
        if holder.is_alive():
            holder.terminate()
            holder.join(5)
    assert holder.exitcode == 0
