"""Bound repeated automatic browser recovery without blocking explicit refresh."""

from __future__ import annotations

from notebooklm_tools.core import auth_recovery_budget as budget


def test_cooldown_failure_cap_and_new_revision(monkeypatch):
    budget._budgets.clear()
    now = [1000.0]
    monkeypatch.setattr(budget.time, "monotonic", lambda: now[0])
    monkeypatch.setenv("NOTEBOOKLM_AUTH_RECOVERY_COOLDOWN_SECONDS", "30")
    monkeypatch.setenv("NOTEBOOKLM_AUTH_MAX_HEADLESS_FAILURES", "2")

    assert budget.allow_automatic_recovery("alpha", "rev1")
    budget.finish_automatic_recovery("alpha", False)
    assert not budget.allow_automatic_recovery("alpha", "rev1")
    now[0] += 31
    assert budget.allow_automatic_recovery("alpha", "rev1")
    budget.finish_automatic_recovery("alpha", False)
    now[0] += 31
    assert not budget.allow_automatic_recovery("alpha", "rev1")
    assert budget.allow_automatic_recovery("alpha", "rev2")


def test_profile_budget_is_isolated_and_success_resets_failures(monkeypatch):
    budget._budgets.clear()
    now = [100.0]
    monkeypatch.setattr(budget.time, "monotonic", lambda: now[0])
    monkeypatch.setenv("NOTEBOOKLM_AUTH_RECOVERY_COOLDOWN_SECONDS", "0")
    monkeypatch.setenv("NOTEBOOKLM_AUTH_MAX_HEADLESS_FAILURES", "1")

    assert budget.allow_automatic_recovery("alpha", None)
    budget.finish_automatic_recovery("alpha", False)
    assert not budget.allow_automatic_recovery("alpha", None)
    assert budget.allow_automatic_recovery("beta", None)
    budget.finish_automatic_recovery("beta", True)
    assert budget.allow_automatic_recovery("beta", None)


def test_invalid_environment_values_use_safe_defaults(monkeypatch):
    budget._budgets.clear()
    monkeypatch.setenv("NOTEBOOKLM_AUTH_RECOVERY_COOLDOWN_SECONDS", "not-a-number")
    monkeypatch.setenv("NOTEBOOKLM_AUTH_MAX_HEADLESS_FAILURES", "not-a-number")
    assert budget.allow_automatic_recovery("alpha", None)
    budget.finish_automatic_recovery("alpha", False)
    assert not budget.allow_automatic_recovery("alpha", None)


def test_concurrent_clients_share_recovery_tokens(monkeypatch):
    import threading
    from types import SimpleNamespace

    from notebooklm_tools.core.base import BaseClient

    budget._budgets.clear()
    budget._inflight.clear()
    monkeypatch.delenv("NOTEBOOKLM_DISABLE_HEADLESS_REFRESH", raising=False)
    monkeypatch.setenv("NOTEBOOKLM_AUTH_RECOVERY_COOLDOWN_SECONDS", "900")
    old = SimpleNamespace(cookies={"SID": "old"}, revision="old")
    renewed = SimpleNamespace(
        cookies={"SID": "new"},
        csrf_token="new-csrf",
        session_id="new-session",
        build_label="new-bl",
        base_host="notebook.google.com",
        revision="new",
    )
    monkeypatch.setattr("notebooklm_tools.core.auth.load_cached_tokens", lambda **_: old)
    entered, release, waiter_entered = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def recover(**kwargs):
        calls.append(kwargs)
        entered.set()
        assert release.wait(5)
        return renewed

    monkeypatch.setattr("notebooklm_tools.utils.auth_browser.run_headless_auth", recover)

    def client():
        obj = BaseClient.__new__(BaseClient)
        obj._is_env_auth = False
        obj._profile_name = "work"
        obj._auth_revision = "old"
        obj.cookies = old.cookies
        obj._state_lock = threading.Lock()
        return obj

    first, second = client(), client()
    results = []
    errors = []

    def run(obj):
        try:
            results.append(obj._try_reload_or_headless_auth())
        except Exception as exc:
            errors.append(exc)

    a = threading.Thread(target=run, args=(first,))
    b = threading.Thread(target=run, args=(second,))
    a.start()
    try:
        assert entered.wait(5)
        active = budget._inflight["work"]
        original_wait = active.done.wait

        def wait(timeout):
            waiter_entered.set()
            return original_wait(timeout)

        monkeypatch.setattr(active.done, "wait", wait)
        b.start()
        assert waiter_entered.wait(5)
    finally:
        release.set()
        a.join(6)
        if b.ident is not None:
            b.join(6)
    assert not a.is_alive() and not b.is_alive()
    assert not errors
    assert results == [True, True]
    assert len(calls) == 1
    for obj in (first, second):
        assert obj.cookies == renewed.cookies
        assert obj.csrf_token == renewed.csrf_token
        assert obj._auth_revision == "new"


def test_wait_timeout_does_not_launch_or_consume_another_attempt(monkeypatch):
    import threading

    budget._budgets.clear()
    budget._inflight.clear()
    entered, release = threading.Event(), threading.Event()
    calls = []

    def recover():
        calls.append(True)
        entered.set()
        assert release.wait(5)
        return None

    owner = threading.Thread(target=lambda: budget.run_automatic_recovery("work", "v1", recover))
    owner.start()
    try:
        assert entered.wait(5)
        assert budget.run_automatic_recovery("work", "v1", recover, wait_timeout=0) is None
        assert len(calls) == 1
        assert budget._budgets["work"].failures == 0
        assert budget.run_automatic_recovery("other", "v1", lambda: "tokens") == "tokens"
    finally:
        release.set()
        owner.join(6)
    assert not owner.is_alive()
    assert budget._budgets["work"].failures == 1
    assert "work" not in budget._inflight


def test_exception_releases_waiters_and_counts_failure(monkeypatch):
    import pytest

    budget._budgets.clear()
    budget._inflight.clear()

    def fail():
        raise RuntimeError("synthetic recovery failure")

    with pytest.raises(RuntimeError):
        budget.run_automatic_recovery("work", "v1", fail)
    assert budget._budgets["work"].failures == 1
    assert "work" not in budget._inflight


def test_file_mode_cookie_change_resets_failure_budget(monkeypatch):
    import threading
    from types import SimpleNamespace

    from notebooklm_tools.core.base import BaseClient

    budget._budgets.clear()
    budget._inflight.clear()
    monkeypatch.delenv("NOTEBOOKLM_DISABLE_HEADLESS_REFRESH", raising=False)
    monkeypatch.setenv("NOTEBOOKLM_AUTH_RECOVERY_COOLDOWN_SECONDS", "0")
    monkeypatch.setenv("NOTEBOOKLM_AUTH_MAX_HEADLESS_FAILURES", "1")
    cached = SimpleNamespace(cookies={"SID": "synthetic-old"}, revision=None)
    monkeypatch.setattr("notebooklm_tools.core.auth.load_cached_tokens", lambda **_: cached)
    calls = []

    def recover(**kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr("notebooklm_tools.utils.auth_browser.run_headless_auth", recover)
    obj = BaseClient.__new__(BaseClient)
    obj._is_env_auth = False
    obj._profile_name = "file-profile"
    obj._auth_revision = None
    obj.cookies = cached.cookies
    obj._state_lock = threading.Lock()
    assert not obj._try_reload_or_headless_auth()
    assert not obj._try_reload_or_headless_auth()
    assert len(calls) == 1
    cached.cookies = {"SID": "synthetic-new"}
    obj.cookies = cached.cookies  # A client initialized after an external login.
    assert not obj._try_reload_or_headless_auth()
    assert len(calls) == 2
    assert calls[-1]["expected_revision"] is None
