"""Profile listing and switching, used by the MCP `profile` tool.

Switching is per server process ("session") by default. Writing the saved default
is a separate, explicit action because it changes the account for every session.
Listing never opens the OS keystore.
"""

from __future__ import annotations

import json
import os
from typing import Any, TypedDict

from notebooklm_tools.services.errors import NotFoundError, ServiceError

_ENV_COOKIES_MSG = (
    "This server is signed in with NOTEBOOKLM_COOKIES from its settings, which overrides "
    "saved profiles. Remove that setting to switch profiles."
)


class ProfileInfo(TypedDict):
    name: str
    email: str | None
    storage_mode: str | None
    is_saved_default: bool
    is_active: bool


def _email(name: str) -> str | None:
    """Email from the non-secret metadata.json (never decrypts credentials)."""
    from notebooklm_tools.utils.config import get_profile_dir

    try:
        meta = get_profile_dir(name, create=False) / "metadata.json"
        return json.loads(meta.read_text(encoding="utf-8")).get("email")
    except Exception:
        return None


def _existing(name: str) -> str:
    from notebooklm_tools.services.auth_storage import saved_profile_names

    clean = (name or "").strip()
    known = saved_profile_names()
    if clean not in known:
        raise NotFoundError(
            f"Profile '{clean}' not found. Available profiles: {', '.join(known) or '(none)'}",
            hint="Use the profile tool with action='list' to see saved profiles.",
            resource_type="profile",
        )
    return clean


def _refuse_if_env_cookies() -> None:
    if os.environ.get("NOTEBOOKLM_COOKIES"):
        raise ServiceError(_ENV_COOKIES_MSG)


def list_profiles() -> list[ProfileInfo]:
    from notebooklm_tools.services.auth_storage import saved_profile_names
    from notebooklm_tools.utils.config import (
        get_auth_storage_mode,
        get_config,
        get_saved_default_profile,
    )

    saved = get_saved_default_profile()
    active = get_config().auth.default_profile
    rows: list[ProfileInfo] = []
    for name in saved_profile_names():
        try:
            mode: str | None = get_auth_storage_mode(name)
        except Exception:
            mode = None
        rows.append(
            ProfileInfo(
                name=name,
                email=_email(name),
                storage_mode=mode,
                is_saved_default=name == saved,
                is_active=name == active,
            )
        )
    return rows


def get_active_profile() -> dict[str, Any]:
    from notebooklm_tools.utils.config import (
        get_config,
        get_saved_default_profile,
        get_session_profile,
    )

    if os.environ.get("NOTEBOOKLM_COOKIES"):
        source = "env cookies"
    elif get_session_profile():
        source = "session"
    elif os.environ.get("NLM_PROFILE"):
        source = "environment"
    else:
        source = "saved default"
    return {
        "profile": get_config().auth.default_profile,
        "source": source,
        "saved_default": get_saved_default_profile(),
    }


def profile_storage_status(name: str | None = None) -> dict[str, Any]:
    from notebooklm_tools.services.auth_storage import get_storage_status

    return dict(get_storage_status(name))


def switch_session_profile(name: str) -> dict[str, Any]:
    from notebooklm_tools.utils.config import set_session_profile

    _refuse_if_env_cookies()
    clean = _existing(name)
    set_session_profile(clean)
    return {
        "profile": clean,
        "email": _email(clean),
        "scope": "session",
        "message": (
            f"Now using profile '{clean}' until this MCP server restarts. "
            "The saved default is unchanged."
        ),
    }


def make_default_profile(name: str) -> dict[str, Any]:
    from notebooklm_tools.utils.config import (
        get_config,
        reset_config,
        save_config,
        set_session_profile,
    )

    _refuse_if_env_cookies()
    clean = _existing(name)
    if os.environ.get("NLM_PROFILE"):
        raise ServiceError(
            "NLM_PROFILE is set in this server's settings, so the saved default can't be "
            "changed from here. Use a session switch instead."
        )
    set_session_profile(None)
    config = get_config()
    config.auth.default_profile = clean
    save_config(config)
    reset_config()
    return {
        "profile": clean,
        "email": _email(clean),
        "scope": "saved default",
        "message": f"'{clean}' is now the saved default for the CLI and every future session.",
    }
