"""Bound automatic headless authentication attempts per saved profile.

Only automatic RPC recovery uses this budget. Explicit CLI/MCP refresh remains
available to callers. A changed credential revision (or file-mode cookie
fingerprint) resets the budget.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Budget:
    revision: str | None
    last_attempt: float = float("-inf")
    failures: int = 0


_lock = threading.RLock()
_budgets: dict[str, _Budget] = {}


@dataclass
class _Attempt:
    done: threading.Event = field(default_factory=threading.Event)
    result: Any = None


_inflight: dict[str, _Attempt] = {}


def _config_number(name: str, fallback: int) -> int:
    try:
        return max(0, int(os.environ.get(name, str(fallback))))
    except ValueError:
        return fallback


def allow_automatic_recovery(profile: str, revision: str | None) -> bool:
    """Reserve a bounded automatic attempt, or refuse without launching Chrome."""
    cooldown = _config_number("NOTEBOOKLM_AUTH_RECOVERY_COOLDOWN_SECONDS", 900)
    failure_limit = _config_number("NOTEBOOKLM_AUTH_MAX_HEADLESS_FAILURES", 3)
    now = time.monotonic()
    with _lock:
        budget = _budgets.get(profile)
        if budget is None or budget.revision != revision:
            budget = _Budget(revision=revision)
            _budgets[profile] = budget
        if failure_limit and budget.failures >= failure_limit:
            return False
        if now - budget.last_attempt < cooldown:
            return False
        budget.last_attempt = now
        return True


def finish_automatic_recovery(profile: str, success: bool) -> None:
    """Record the result; a successful recovery clears the failure count."""
    with _lock:
        budget = _budgets.get(profile)
        if budget is None:
            return
        budget.failures = 0 if success else budget.failures + 1


def run_automatic_recovery(
    profile: str,
    revision: str | None,
    recover: Callable[[], Any],
    *,
    wait_timeout: float = 60,
) -> Any:
    """Share an in-flight attempt before applying limits to a new attempt."""
    with _lock:
        attempt = _inflight.get(profile)
        owner = attempt is None
        if owner:
            if not allow_automatic_recovery(profile, revision):
                return None
            attempt = _Attempt()
            _inflight[profile] = attempt
    assert attempt is not None
    if not owner:
        return attempt.result if attempt.done.wait(wait_timeout) else None

    try:
        attempt.result = recover()
        return attempt.result
    finally:
        with _lock:
            finish_automatic_recovery(profile, bool(attempt.result))
            del _inflight[profile]
            attempt.done.set()
