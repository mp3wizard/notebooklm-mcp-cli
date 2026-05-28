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
