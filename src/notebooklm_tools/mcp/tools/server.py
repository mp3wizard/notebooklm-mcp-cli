"""Server tools - Server info and version checking."""

import json
import urllib.request
from typing import Any, cast

from notebooklm_tools import __version__

from ._utils import logged_tool


def _get_latest_pypi_version() -> str | None:
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


def _compare_versions(current: str, latest: str) -> bool:
    """Compare version strings to determine if an update is available.

    Returns:
        True if latest is greater than current.
    """
    try:
        # Simple comparison: split by dots and compare numerically
        current_parts = [int(x) for x in current.split(".")]
        latest_parts = [int(x) for x in latest.split(".")]
        return latest_parts > current_parts
    except (ValueError, AttributeError):
        return False


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
    """
    latest = _get_latest_pypi_version()
    update_available = False

    if latest:
        update_available = _compare_versions(__version__, latest)

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

    return info
