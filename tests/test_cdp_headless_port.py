"""Headless auth must not launch on a hardcoded port that a foreign process
may already hold, which would let it probe the wrong browser (issue #330)."""

from unittest.mock import patch

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
