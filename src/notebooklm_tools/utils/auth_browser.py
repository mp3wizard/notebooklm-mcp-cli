"""Browser/backend selection for interactive and headless authentication."""

import json
from typing import Any

from notebooklm_tools.core.exceptions import AuthenticationError
from notebooklm_tools.utils.config import get_config, get_profile_dir

CHROMIUM_BROWSER_KEYS = {"auto", "chrome", "arc", "brave", "edge", "chromium", "vivaldi", "opera"}
FIREFOX_BROWSER_KEY = "firefox"


def _normalize_browser(preferred: str | None = None) -> str:
    if preferred is None:
        preferred = get_config().auth.browser
    return (preferred or "auto").lower().strip()


def get_supported_auth_browsers() -> list[str]:
    """Return user-facing browser names for auth."""
    from notebooklm_tools.utils.cdp import get_supported_browsers as get_supported_chromium_browsers

    browsers = get_supported_chromium_browsers()
    from notebooklm_tools.utils.firefox import get_firefox_path

    if get_firefox_path():
        browsers.append("Firefox")
    return browsers


def select_auth_backend(preferred: str | None = None) -> dict[str, str] | None:
    """Pick the best available auth backend for the configured browser."""
    from notebooklm_tools.utils.cdp import _get_chromium_path, get_browser_display_name
    from notebooklm_tools.utils.firefox import get_firefox_path

    preferred = _normalize_browser(preferred)

    if preferred == FIREFOX_BROWSER_KEY:
        if get_firefox_path():
            return {"backend": "firefox_profile", "browser": "Firefox"}
        return None

    chromium_path = _get_chromium_path(preferred if preferred in CHROMIUM_BROWSER_KEYS else "auto")
    if chromium_path:
        return {"backend": "chromium_cdp", "browser": get_browser_display_name()}

    if preferred == "auto" and get_firefox_path():
        return {"backend": "firefox_profile", "browser": "Firefox"}

    return None


def extract_cookies_via_browser(
    *,
    profile_name: str = "default",
    clear_profile: bool = False,
    login_timeout: int = 300,
    wait_for_login: bool = True,
    preferred: str | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Extract auth cookies using the selected backend."""
    backend = select_auth_backend(preferred)
    if not backend:
        if _normalize_browser(preferred) == FIREFOX_BROWSER_KEY:
            from notebooklm_tools.utils.firefox import ensure_firefox_available

            ensure_firefox_available()
        browsers = get_supported_auth_browsers()
        if len(browsers) > 1:
            browser_text = ", ".join(browsers[:-1]) + f", or {browsers[-1]}"
        elif browsers:
            browser_text = browsers[0]
        else:
            browser_text = "a supported browser"
        raise AuthenticationError(
            message="No supported browser found",
            hint=f"Install {browser_text}, or use 'nlm login --manual' to import cookies from a file.",
        )

    if backend["backend"] == "firefox_profile":
        from notebooklm_tools.utils.firefox import extract_cookies_via_firefox

        result = extract_cookies_via_firefox(
            wait_for_login=wait_for_login,
            login_timeout=login_timeout,
            profile_name=profile_name,
            clear_profile=clear_profile,
        )
        return result, backend

    from notebooklm_tools.utils.cdp import extract_cookies_via_cdp

    result = extract_cookies_via_cdp(
        auto_launch=True,
        wait_for_login=wait_for_login,
        login_timeout=login_timeout,
        profile_name=profile_name,
        clear_profile=clear_profile,
    )
    return result, backend


def _get_saved_browser_backend(profile_name: str) -> str | None:
    metadata_file = get_profile_dir(profile_name) / "metadata.json"
    if not metadata_file.exists():
        return None
    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    value = metadata.get("browser_backend")
    return value if isinstance(value, str) and value else None


def run_headless_auth(profile_name: str = "default", timeout: int = 30) -> Any | None:
    """Try headless auth using the profile's saved backend, then reasonable fallbacks."""
    preferred_backend = _get_saved_browser_backend(profile_name)
    attempts: list[str] = []

    if preferred_backend in {"chromium_cdp", "firefox_profile"}:
        attempts.append(preferred_backend)

    selected = select_auth_backend()
    if selected and selected["backend"] not in attempts:
        attempts.append(selected["backend"])

    if "chromium_cdp" not in attempts:
        attempts.append("chromium_cdp")

    for backend in attempts:
        if backend == "chromium_cdp":
            from notebooklm_tools.utils.cdp import run_headless_auth as run_headless_chromium_auth

            tokens = run_headless_chromium_auth(timeout=timeout, profile_name=profile_name)
            if tokens:
                return tokens
            continue
        if backend == "firefox_profile":
            from notebooklm_tools.utils.firefox import (
                run_headless_auth as run_headless_firefox_auth,
            )

            tokens = run_headless_firefox_auth(timeout=timeout, profile_name=profile_name)
            if tokens:
                return tokens

    return None
