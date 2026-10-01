"""Persistent non-secret state for user awareness notices, probes, and prompts.

Stored at ~/.notebooklm-mcp-cli/notices.json.
Tracks:
- cli_notice_shown: bool (whether the one-time TTY banner was displayed)
- mcp_notice_shown: bool (whether the one-time MCP tool response notice was delivered)
- probe: cached result of the OS keystore availability probe and timestamp (30-day TTL)
- protect_answered: map of profile_name -> "yes" | "no" shared across wizard and login
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from pathlib import Path
from typing import Any

PROBE_TTL_SECONDS = 30 * 86400.0  # 30 days


def _get_notices_file(storage_dir: Path | None = None) -> Path:
    from notebooklm_tools.utils.config import get_storage_dir

    root = storage_dir if storage_dir is not None else get_storage_dir()
    return root / "notices.json"


def load_notices(storage_dir: Path | None = None) -> dict[str, Any]:
    """Read the notices state dictionary."""
    notices_file = _get_notices_file(storage_dir)
    if not notices_file.exists():
        return {}
    try:
        data = json.loads(notices_file.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_notices(data: dict[str, Any], storage_dir: Path | None = None) -> None:
    """Save the notices state atomically with restrictive permissions."""
    notices_file = _get_notices_file(storage_dir)
    notices_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = notices_file.parent / f"{notices_file.name}.tmp.{os.getpid()}"
    try:
        content = (json.dumps(data, indent=2) + "\n").encode("utf-8")
        fd = os.open(str(tmp), os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        try:
            os.write(fd, content)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, notices_file)
    except Exception:
        with contextlib.suppress(Exception):
            if tmp.exists():
                tmp.unlink()


def is_cli_notice_shown(storage_dir: Path | None = None) -> bool:
    """True if the one-time CLI storage notice was already displayed."""
    return bool(load_notices(storage_dir).get("cli_notice_shown", False))


def mark_cli_notice_shown(storage_dir: Path | None = None) -> None:
    """Record that the one-time CLI storage notice was displayed."""
    notices = load_notices(storage_dir)
    notices["cli_notice_shown"] = True
    save_notices(notices, storage_dir)


def is_mcp_notice_shown(storage_dir: Path | None = None) -> bool:
    """True if the one-time MCP storage notice was already delivered."""
    return bool(load_notices(storage_dir).get("mcp_notice_shown", False))


def mark_mcp_notice_shown(storage_dir: Path | None = None) -> None:
    """Record that the one-time MCP storage notice was delivered."""
    notices = load_notices(storage_dir)
    notices["mcp_notice_shown"] = True
    save_notices(notices, storage_dir)


def get_protect_answer(profile_name: str, storage_dir: Path | None = None) -> str | None:
    """Get the user's answer to the 'Protect this login?' prompt ('yes', 'no', or None)."""
    notices = load_notices(storage_dir)
    answered = notices.get("protect_answered", {})
    if isinstance(answered, dict):
        return answered.get(profile_name)
    return None


def record_protect_answer(profile_name: str, answer: str, storage_dir: Path | None = None) -> None:
    """Record the user's answer ('yes' or 'no') for a profile so they are not asked again."""
    notices = load_notices(storage_dir)
    answered = notices.setdefault("protect_answered", {})
    if not isinstance(answered, dict):
        answered = {}
        notices["protect_answered"] = answered
    answered[profile_name] = answer.strip().lower()
    save_notices(notices, storage_dir)


def get_cached_probe_result(
    max_age_seconds: float = PROBE_TTL_SECONDS,
    storage_dir: Path | None = None,
) -> bool | None:
    """Return cached keystore availability probe result if fresh, else None."""
    notices = load_notices(storage_dir)
    probe = notices.get("probe")
    if isinstance(probe, dict):
        checked_at = probe.get("checked_at")
        result = probe.get("result")
        if isinstance(checked_at, (int, float)) and (time.time() - checked_at) < max_age_seconds:
            if result == "available":
                return True
            elif result == "unavailable":
                return False
    return None


def cache_probe_result(available: bool, storage_dir: Path | None = None) -> None:
    """Cache the result of an OS keystore availability probe."""
    notices = load_notices(storage_dir)
    notices["probe"] = {
        "result": "available" if available else "unavailable",
        "checked_at": time.time(),
    }
    save_notices(notices, storage_dir)
