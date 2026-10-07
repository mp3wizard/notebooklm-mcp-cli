"""Headless auth must not launch on a hardcoded port that a foreign process
may already hold, which would let it probe the wrong browser (issue #330)."""

from unittest.mock import patch

import pytest

from notebooklm_tools.utils import cdp


def test_headless_auth_uses_free_port_when_launching():
    """A fresh headless launch picks a free port instead of the default 9223."""
    with (
        patch.object(cdp, "has_chrome_profile", return_value=True),
        patch.object(cdp, "find_existing_nlm_chrome", return_value=(None, None)),
        patch.object(cdp, "find_available_port", return_value=9999) as free_port,
        patch.object(cdp, "launch_chrome_process", return_value=None) as launch,
    ):
        result = cdp.run_headless_auth(port=9223, profile_name="work")

    assert result is None  # bailed out after launch returned None
    free_port.assert_called_once_with(starting_from=9223)
    launch.assert_called_once_with(9999, headless=True, profile_name="work")


def test_headless_auth_keeps_best_effort_port_failure_compatible():
    """Automatic recovery must keep returning None for infrastructure failures."""
    with (
        patch.object(cdp, "has_chrome_profile", return_value=True),
        patch.object(cdp, "find_existing_nlm_chrome", return_value=(None, None)),
        patch.object(
            cdp,
            "find_available_port",
            side_effect=RuntimeError("No available ports in range 9222-9231."),
        ),
    ):
        result = cdp.run_headless_auth(port=9222, profile_name="work")

    assert result is None


def test_headless_auth_can_surface_safe_port_failure():
    """Explicit refresh diagnostics should preserve an actionable CDP failure."""
    from notebooklm_tools.core.exceptions import AuthenticationError

    with (
        patch.object(cdp, "has_chrome_profile", return_value=True),
        patch.object(cdp, "find_existing_nlm_chrome", return_value=(None, None)),
        patch.object(
            cdp,
            "find_available_port",
            side_effect=RuntimeError("No available ports in range 9222-9231."),
        ),
        pytest.raises(AuthenticationError, match="9222-9231") as exc_info,
    ):
        cdp.run_headless_auth(
            port=9222,
            profile_name="work",
            raise_on_error=True,
        )

    assert "nlm login" in str(exc_info.value).lower()


def test_headless_auth_reports_unsigned_saved_profile_for_explicit_refresh():
    """Explicit refresh should explain when the managed browser is simply signed out."""
    from notebooklm_tools.core.exceptions import AuthenticationError

    page = {"webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1"}
    with (
        patch.object(cdp, "has_chrome_profile", return_value=True),
        patch.object(cdp, "find_existing_nlm_chrome", return_value=(9223, "http://127.0.0.1:9223")),
        patch.object(cdp, "find_or_create_notebooklm_page", return_value=page),
        pytest.raises(AuthenticationError, match="not signed in") as exc_info,
    ):
        cdp.run_headless_auth(
            port=9223,
            timeout=0,
            profile_name="work",
            raise_on_error=True,
        )

    assert "nlm login" in str(exc_info.value).lower()


def test_headless_auth_keeps_unsigned_saved_profile_best_effort_compatible():
    """Automatic recovery should still collapse a signed-out saved profile to None."""
    page = {"webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1"}
    with (
        patch.object(cdp, "has_chrome_profile", return_value=True),
        patch.object(cdp, "find_existing_nlm_chrome", return_value=(9223, "http://127.0.0.1:9223")),
        patch.object(cdp, "find_or_create_notebooklm_page", return_value=page),
    ):
        result = cdp.run_headless_auth(port=9223, timeout=0, profile_name="work")

    assert result is None


def test_headless_auth_reports_candidate_rejection_for_explicit_refresh():
    """Explicit refresh should distinguish provider rejection from browser launch failures."""
    from notebooklm_tools.core.exceptions import AuthenticationError

    page = {"webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1"}
    cookies = [{"name": "SID", "value": "fresh", "domain": ".google.com"}]
    with (
        patch.object(cdp, "has_chrome_profile", return_value=True),
        patch.object(cdp, "find_existing_nlm_chrome", return_value=(9223, "http://127.0.0.1:9223")),
        patch.object(cdp, "find_or_create_notebooklm_page", return_value=page),
        patch.object(cdp, "get_current_url", return_value="https://notebook.google.com/"),
        patch.object(cdp, "is_logged_in", return_value=True),
        patch.object(cdp, "_wait_for_page_ready", return_value=("<html></html>", True)),
        patch.object(cdp, "get_page_cookies", return_value=cookies),
        patch("notebooklm_tools.core.auth.validate_cookies", return_value=True),
        patch.object(cdp, "extract_csrf_token", return_value="csrf"),
        patch.object(cdp, "extract_session_id", return_value="session"),
        patch.object(cdp, "_validate_headless_candidate", return_value=False),
        pytest.raises(AuthenticationError, match="rejected the credentials") as exc_info,
    ):
        cdp.run_headless_auth(
            port=9223,
            timeout=1,
            profile_name="work",
            raise_on_error=True,
        )

    assert "nlm login" in str(exc_info.value).lower()
