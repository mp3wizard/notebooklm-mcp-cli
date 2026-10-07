"""Server tools - Server info and version checking."""

import json
import threading
import time
import urllib.request
from typing import Any, cast

from notebooklm_tools import __version__
from notebooklm_tools.utils.versioning import is_newer_version

from ._utils import logged_tool

_VERSION_CACHE_TTL_SECONDS = 86400
_VERSION_FAILURE_CACHE_TTL_SECONDS = 300
_version_cache_lock = threading.Lock()
_version_cache: tuple[float, str | None] | None = None


def _fetch_latest_pypi_version() -> str | None:
    """Fetch the latest version from PyPI.

    Returns:
        Latest version string or None if fetch fails.
    """
    try:
        url = "https://pypi.org/pypi/notebooklm-mcp-cli/json"
        req = urllib.request.Request(url, headers={"User-Agent": "notebooklm-mcp-cli"})
        with urllib.request.urlopen(req, timeout=2) as response:  # nosec B310 — URL is hardcoded to https://pypi.org
            data = cast(dict[str, Any], json.loads(response.read().decode()))
            info = data.get("info")
            if isinstance(info, dict):
                version = info.get("version")
                if isinstance(version, str):
                    return version
    except Exception:
        return None
    return None


def _get_latest_pypi_version() -> str | None:
    """Return the latest PyPI version with bounded process-local caching.

    Successful lookups are reused for 24 hours. Failed lookups are cached for
    five minutes so an offline long-lived MCP server does not pay the two-second
    network timeout on every server_info() call.
    """
    global _version_cache

    def _cached_value(now: float) -> tuple[bool, str | None]:
        cached = _version_cache
        if cached is None:
            return False, None
        checked_at, latest = cached
        ttl = (
            _VERSION_CACHE_TTL_SECONDS if latest is not None else _VERSION_FAILURE_CACHE_TTL_SECONDS
        )
        if now - checked_at < ttl:
            return True, latest
        return False, None

    now = time.monotonic()
    fresh, latest = _cached_value(now)
    if fresh:
        return latest

    with _version_cache_lock:
        now = time.monotonic()
        fresh, latest = _cached_value(now)
        if fresh:
            return latest
        latest = _fetch_latest_pypi_version()
        _version_cache = (now, latest)
        return latest


def _check_auth_status() -> str:
    """Use AuthHealthChecker to determine the stable auth status string.

    The AuthHealthChecker runs a multi-probe strategy (homepage + API
    fallback) with TTL caching and mtime-based invalidation, providing
    more reliable results than a single homepage fetch. Results are
    cached for 30 seconds and bypassed on auth-file changes, so this
    is not strictly a "live" check on every call.
    """
    try:
        from notebooklm_tools.services.auth import get_auth_health_checker

        return str(get_auth_health_checker().check().status)
    except Exception:
        return "error"


def _runtime_capabilities(
    registered_tools: set[str] | None = None,
    disabled_tools: set[str] | None = None,
) -> dict[str, Any]:
    """Describe built-in MCP capability visibility without probing provider features.

    This is intentionally a runtime/tool-surface report. It does not infer
    account entitlements, quota, secure-computer access, or undocumented
    provider capabilities from plan labels.
    """
    from notebooklm_tools.mcp import tool_groups
    from notebooklm_tools.mcp.tools._utils import _tool_registry

    registered = (
        {name for name, _ in _tool_registry} if registered_tools is None else set(registered_tools)
    )
    disabled = tool_groups._resolve_disabled() if disabled_tools is None else set(disabled_tools)
    visible = registered - disabled

    groups: dict[str, dict[str, Any]] = {}
    grouped_tools: set[str] = set()
    for group_name, configured_tools in sorted(tool_groups.TOOL_GROUPS.items()):
        grouped_tools |= configured_tools
        visible_tools = configured_tools & visible
        hidden_tools = configured_tools & registered & disabled
        missing_tools = configured_tools - registered
        available = bool(configured_tools) and configured_tools <= visible
        groups[group_name] = {
            "available": available,
            "partially_available": bool(visible_tools) and not available,
            "visible_tools": sorted(visible_tools),
            "hidden_tools": sorted(hidden_tools),
            "missing_tools": sorted(missing_tools),
        }

    return {
        "schema_version": 1,
        "scope": "built_in_mcp_runtime",
        "source": "registered_tool_visibility",
        "registered_tool_count": len(registered),
        "visible_tool_count": len(visible),
        "hidden_tool_count": len(registered - visible),
        "groups": groups,
        "ungrouped_tools": sorted(registered - grouped_tools),
    }


def _check_storage_warning() -> str | None:
    """Return a short one-line storage warning if a conflict or pending operation exists.

    Never touches the OS keystore in file mode and never raises.
    """
    try:
        from notebooklm_tools.services.auth_storage import get_storage_status

        status = get_storage_status()
        if status.get("has_conflict"):
            return "Storage conflict detected. Run 'nlm auth storage resolve'."
        if status.get("has_pending_op"):
            return "Pending storage operation detected. Run 'nlm auth storage status'."
        if status.get("protected_residue"):
            return "Protected storage residue present. Run 'nlm auth storage resolve file'."
        return None
    except Exception:
        return None


def _profile_summary() -> dict[str, Any]:
    """Saved profiles with storage mode and problems - metadata only, never the keystore."""
    from ...services import profiles as profile_service

    try:
        rows = []
        for row in profile_service.list_profiles():
            try:
                st = profile_service.profile_storage_status(row["name"])
            except Exception:
                st = {}
            rows.append(
                {
                    **row,
                    "has_conflict": bool(st.get("has_conflict")),
                    "has_pending_op": bool(st.get("has_pending_op")),
                }
            )
        return {"active_profile": profile_service.get_active_profile(), "profiles": rows}
    except Exception as exc:
        return {"active_profile": None, "profiles": [], "profiles_error": str(exc)}


@logged_tool()
def server_info() -> dict[str, Any]:
    """Get version, auth status, and conservative MCP capability visibility.

    AI assistants: If update_available is True, inform the user that a new
    version is available and suggest updating with the provided command.

    auth_status is the result of an AuthHealthChecker probe. The checker
    runs a multi-probe strategy (homepage fetch + API fallback) with
    30-second TTL caching and mtime-based bypass on auth-file changes.
    The reported value may therefore be up to 30 seconds old, and an
    external `nlm login` is picked up within one check cycle without
    waiting for the TTL to expire.

    auth_status meanings:
    - "configured"     — homepage (or API fallback) check passed; credentials
                         are good. Cached credentials may be reported as
                         configured for up to 30 seconds.
    - "not_configured" — no credentials are stored (first-time setup).
    - "stale"          — credentials are known-bad (expired or past the
                         7-day heuristic). Operations will fail; ask the
                         user to run `nlm login` to refresh.
    - "unverified"     — the check could not be completed (network error,
                         timeout, non-200 response). Cached credentials may
                         still work for actual API calls, so do not assume
                         the user needs to re-auth.
    - "error"          — unexpected exception inside the check itself.

    Returns:
        dict with version info:
        - version: Current installed version
        - latest_version: Latest version on PyPI (or None if check failed)
        - update_available: True if a newer version is available
        - auth_status: configured | stale | unverified | not_configured | error
        - storage_warning: Short warning if conflict/pending op exists (or None)
        - update_command: Command to run to update
        - mcp_capabilities: Built-in tool groups visible in this server process
        - provider_capabilities: Explicitly unprobed provider/account capabilities
    - active_profile: Which saved account is in use and why (session switch or saved default)
    - profiles: Saved accounts with email, storage mode (plain/protected) and any storage
      problems. Metadata only; never opens the OS keystore.
    """
    latest = _get_latest_pypi_version()
    update_available = False

    if latest:
        update_available = is_newer_version(__version__, latest)

    info: dict[str, Any] = {
        "status": "success",
        "version": __version__,
        "latest_version": latest,
        "update_available": update_available,
        "auth_status": _check_auth_status(),
        "storage_warning": _check_storage_warning(),
        "update_command": "uv tool upgrade notebooklm-mcp-cli",
        "pip_update_command": "pip install --upgrade notebooklm-mcp-cli",
        "mcp_capabilities": _runtime_capabilities(),
        "provider_capabilities": {
            "status": "not_probed",
            "reason": (
                "server_info reports MCP runtime visibility only; account plan labels "
                "are not treated as provider capability evidence."
            ),
        },
    }

    info.update(_profile_summary())
    return info
