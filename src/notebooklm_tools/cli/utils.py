import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import typer
from rich.console import Console

from notebooklm_tools import __version__
from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.core.client import NotebookLMClient
from notebooklm_tools.utils.config import get_config, get_storage_dir


def make_console(**kwargs) -> "Console":
    """Create a Rich Console that is safe on Windows legacy codepage terminals.

    Windows consoles using cp1251/cp1252 etc. cannot encode certain Unicode
    characters that Rich uses by default (e.g. checkmark ✓ U+2713). Setting
    ``safe_box=True`` replaces box-drawing chars with ASCII fallbacks.
    Rich also auto-detects the terminal encoding on Windows via ``PYTHONIOENCODING``
    or the system locale — but this ensures we never crash even without that override.

    See: https://github.com/jacob-bd/notebooklm-mcp-cli/issues/105
    """
    kwargs.setdefault("safe_box", True)
    if sys.platform == "win32":
        # Avoid Rich legacy Windows renderer path that encodes with cp1252 (Issue #156).
        kwargs.setdefault("legacy_windows", False)
    return Console(**kwargs)


console = make_console()


def get_client(profile: str | None = None) -> NotebookLMClient:
    """Get an authenticated NotebookLM client.

    Args:
        profile: Optional profile name. Uses config default_profile if not specified.

    Tries to load cached tokens first. If unavailable, guides the user to login.
    """
    # 1. Try environment variables first (most explicit)
    env_cookies = os.environ.get("NOTEBOOKLM_COOKIES")
    if env_cookies:
        return NotebookLMClient(cookies=extract_cookies_from_string(env_cookies))

    # 2. Try loading specified profile, or fall back to config default
    if not profile:
        profile = get_config().auth.default_profile
    manager = AuthManager(profile)
    if not manager.profile_exists():
        console.print(
            f"[red]Error:[/red] Profile '{manager.profile_name}' not found. Run 'nlm login' first."
        )
        raise typer.Exit(1)

    try:
        p = manager.load_profile()
        return NotebookLMClient(
            cookies=p.cookies,
            csrf_token=p.csrf_token or "",
            session_id=p.session_id or "",
            build_label=p.build_label or "",
        )
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[yellow]Authentication error:[/yellow] {e}")
        console.print("Please run: [bold]nlm login[/bold]")
        raise typer.Exit(1) from e


def handle_error(e: Exception, json_output: bool = False) -> None:
    """Standard error handler for CLI commands."""
    from notebooklm_tools.cli.formatters import print_json
    from notebooklm_tools.core.exceptions import NLMError
    from notebooklm_tools.services.errors import ServiceError

    if isinstance(e, typer.Exit):
        raise e

    msg = str(e)
    hint = getattr(e, "hint", None)

    if isinstance(e, ServiceError):
        msg = e.user_message
    elif isinstance(e, NLMError):
        msg = e.message

    if json_output:
        err = {"status": "error", "error": msg}
        if hint:
            err["hint"] = hint
        print_json(err)
    else:
        if isinstance(e, (ServiceError, NLMError)):
            console.print(f"[red]Error:[/red] {msg}")
            if hint:
                console.print(f"\n[dim]Hint: {hint}[/dim]")
        else:
            # Unexpected error
            console.print(f"[red]Unexpected Error:[/red] {msg}")

    raise typer.Exit(1)


def extract_cookies_from_string(cookie_str: str) -> dict[str, str]:
    """Helper to parse raw cookie string."""
    cookies = {}
    if not cookie_str:
        return cookies
    for item in cookie_str.split(";"):
        if "=" in item:
            key, value = item.split("=", 1)
            key = key.strip()
            if key:
                cookies[key] = value.strip()
    return cookies


# ========== Version Check Utilities ==========


def _get_cache_path() -> Path:
    """Get path to version check cache file."""
    cache_dir = get_storage_dir() / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "update_check.json"


def _get_cached_version_info() -> dict | None:
    """Load cached version info if still valid (within 24 hours)."""
    cache_path = _get_cache_path()
    if not cache_path.exists():
        return None

    try:
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)

        # Check if cache is still valid (24 hours = 86400 seconds)
        if time.time() - data.get("checked_at", 0) < 86400:
            return data
    except (json.JSONDecodeError, OSError):
        pass

    return None


def _save_version_cache(latest_version: str) -> None:
    """Save version info to cache."""
    cache_path = _get_cache_path()
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "latest_version": latest_version,
                    "checked_at": time.time(),
                },
                f,
            )
    except OSError:
        pass  # Silently ignore cache write failures


def _fetch_latest_version() -> str | None:
    """Fetch latest version from PyPI with 2 second timeout."""
    try:
        url = "https://pypi.org/pypi/notebooklm-mcp-cli/json"
        req = urllib.request.Request(url, headers={"User-Agent": "notebooklm-mcp-cli"})
        with urllib.request.urlopen(req, timeout=2) as response:  # nosec B310 — URL is hardcoded to https://pypi.org
            data = json.loads(response.read().decode())
            return data.get("info", {}).get("version")
    except Exception:
        return None


def _compare_versions(current: str, latest: str) -> bool:
    """Compare version strings. Returns True if latest > current."""
    try:
        current_parts = [int(x) for x in current.split(".")]
        latest_parts = [int(x) for x in latest.split(".")]
        return latest_parts > current_parts
    except (ValueError, AttributeError):
        return False


def check_for_updates() -> tuple[bool, str | None]:
    """Check if a new version is available.

    Returns:
        Tuple of (update_available, latest_version).
        Uses cached result if available and fresh.
    """
    # Check cache first
    cached = _get_cached_version_info()
    if cached:
        latest = cached.get("latest_version")
        if latest:
            return _compare_versions(__version__, latest), latest

    # Fetch from PyPI
    latest = _fetch_latest_version()
    if latest:
        _save_version_cache(latest)
        return _compare_versions(__version__, latest), latest

    return False, None


def print_update_notification() -> None:
    """Print update notification if available. Call after command execution."""
    # Only show in TTY (not when piping output)
    import sys

    if not sys.stdout.isatty():
        return

    update_available, latest = check_for_updates()
    if update_available and latest:
        console.print()
        console.print(
            f"[dim]🔔 Update available:[/dim] [cyan]{__version__}[/cyan] → [green]{latest}[/green]. "
            f"[dim]Run[/dim] [bold]uv tool upgrade notebooklm-mcp-cli[/bold] [dim]to update.[/dim]"
        )
