"""Regression tests for ``is_logged_in()`` URL detection.

Background: ``is_logged_in(url)`` previously used a substring match
(``if "accounts.google.com" in url``) against the full URL string. After
Google sign-in, NotebookLM appends ``?original_referer=https://accounts.google.com#``
to the redirect target, which caused the substring check to fire and
report "not logged in" -- making ``nlm login`` time out after 5 minutes
even though the browser was fully signed in.

The fix parses the URL hostname instead of substring-matching the full URL.
"""

import pytest

from notebooklm_tools.utils import cdp
from notebooklm_tools.utils.cdp import _is_notebooklm_url, is_logged_in


@pytest.mark.parametrize(
    "url, expected",
    [
        # Plain logged-in URLs.
        ("https://notebooklm.google.com/", True),
        ("https://notebooklm.google.com/some/notebook/abc", True),
        # Regression: NotebookLM appends ?original_referer=... right after
        # Google sign-in. The substring `accounts.google.com` IS present in
        # the URL (inside the query string), but the user is signed in.
        (
            "https://notebooklm.google.com/?original_referer=https%3A%2F%2Faccounts.google.com%23",
            True,
        ),
        # Defensive: an unrelated query string mentioning accounts.google.com
        # must not be confused with a sign-in redirect.
        ("https://notebooklm.google.com/?ref=https://accounts.google.com", True),
        # Enterprise NotebookLM host.
        ("https://notebooklm.cloud.google.com/", True),
        ("https://notebooklm.cloud.google.com/notebook/abc", True),
        # Google's "Gemini Notebook" rebrand host (issue #269).
        ("https://notebook.google.com/", True),
        ("https://notebook.google.com/notebook/abc", True),
        (
            "https://notebook.google.com/?original_referer=https%3A%2F%2Faccounts.google.com%23",
            True,
        ),
        # Workspace/enterprise variant of the rebrand host (issue #270).
        ("https://notebook.cloud.google.com/", True),
        # Standard Google sign-in redirect: not logged in.
        ("https://accounts.google.com/v3/signin/identifier?continue=...", False),
        ("https://accounts.google.com/", False),
        # Hostname spoofing on the accounts.google.com side must not be treated
        # as a sign-in redirect (the regression this PR fixes was the inverse:
        # treating a query-string mention of accounts.google.com as a redirect).
        ("https://evil.accounts.google.com.example.com/", False),
        # Unrelated domains.
        ("https://example.com/", False),
        # Edge cases: empty / malformed URLs must default to "not logged in".
        ("", False),
        ("not a url at all", False),
    ],
)
def test_is_logged_in(url: str, expected: bool) -> None:
    assert is_logged_in(url) is expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://notebooklm.google.com/", True),
        ("https://notebooklm.cloud.google.com/notebook/abc", True),
        ("https://notebook.google.com/", True),
        ("https://notebook.cloud.google.com/", True),
        (
            "https://accounts.google.com/v3/signin/identifier"
            "?continue=https%3A%2F%2Fnotebooklm.google.com%2F",
            False,
        ),
        ("https://example.com/?next=https://notebooklm.google.com/", False),
        ("", False),
    ],
)
def test_is_notebooklm_url_checks_hostname_only(url: str, expected: bool) -> None:
    assert _is_notebooklm_url(url) is expected


def test_find_or_create_notebooklm_page_ignores_accounts_continue_url(monkeypatch) -> None:
    pages = [
        {
            "type": "page",
            "url": (
                "https://accounts.google.com/v3/signin/identifier"
                "?continue=https%3A%2F%2Fnotebooklm.google.com%2F"
            ),
            "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/signin",
        }
    ]

    class Response:
        status_code = 200
        text = '{"url":"https://notebooklm.google.com/"}'

        @staticmethod
        def json() -> dict[str, str]:
            return {
                "url": "https://notebooklm.google.com/",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/new",
            }

    monkeypatch.setattr(cdp, "get_pages_by_cdp_url", lambda _: pages)
    monkeypatch.setattr(cdp.httpx_client, "put", lambda *_, **__: Response())

    page = cdp.find_or_create_notebooklm_page_by_cdp_url("http://127.0.0.1:9223")

    assert page is not None
    assert page["url"] == "https://notebooklm.google.com/"


def test_extract_cookies_via_cdp_reports_chrome_handoff(monkeypatch) -> None:
    """Regression test for issue #272's secondary bug.

    When Chrome is already running (but not owned by our profile / not found on a
    known port), the browser we launch hands off to it and exits immediately, so the
    debug port never binds. The error raised must point the user at fully quitting
    Chrome, not at the meaningless port number.
    """
    from notebooklm_tools.core.exceptions import AuthenticationError

    class FakeExitedProcess:
        stderr = None

        def poll(self) -> int:
            return 0

    def fake_launch_chrome(port, profile_name="default") -> bool:
        cdp._chrome_process = FakeExitedProcess()
        cdp._chrome_port = port
        return True

    monkeypatch.setattr(cdp, "_kill_stale_nlm_browsers", lambda: None)
    monkeypatch.setattr(cdp, "find_existing_nlm_chrome", lambda **_: (None, None))
    monkeypatch.setattr(cdp, "get_chrome_path", lambda: "/fake/chrome")
    monkeypatch.setattr(cdp, "is_profile_locked", lambda *_a, **_k: False)
    monkeypatch.setattr(cdp, "_get_profile_dir_for_launch", lambda *_a, **_k: "/fake/profile")
    monkeypatch.setattr(cdp, "find_available_port", lambda: 9222)
    monkeypatch.setattr(cdp, "launch_chrome", fake_launch_chrome)
    monkeypatch.setattr(cdp, "get_debugger_url", lambda *_a, **_k: None)

    try:
        with pytest.raises(AuthenticationError) as exc_info:
            cdp.extract_cookies_via_cdp(profile_name="default")

        error = exc_info.value
        assert "already running" in str(error.message).lower()
        assert "quit chrome" in str(error.hint).lower()
    finally:
        cdp._chrome_process = None
        cdp._chrome_port = None
