from __future__ import annotations

from notebooklm_tools.services.auth_replay import (
    AuthReplayProbe,
    _classify_auth_replay,
    _diagnostic_rpc_headers,
)


def test_auth_replay_classifies_normal_httpx_success():
    report = _classify_auth_replay(
        "default",
        [
            AuthReplayProbe("httpx_saved", True, True, notebook_count=3),
            AuthReplayProbe("httpx_after_rotate", True, True, notebook_count=3),
        ],
    )

    assert report.verdict == "httpx_ok"
    assert "normal httpx" in report.recommendation


def test_auth_replay_classifies_cookie_freshness():
    report = _classify_auth_replay(
        "default",
        [
            AuthReplayProbe("httpx_saved", True, False, error="ClientAuthenticationError"),
            AuthReplayProbe("httpx_after_rotate", True, True, notebook_count=3),
        ],
    )

    assert report.verdict == "cookie_freshness"
    assert "RotateCookies" in report.recommendation


def test_auth_replay_classifies_browser_bound_replay():
    report = _classify_auth_replay(
        "default",
        [
            AuthReplayProbe("httpx_saved", True, False, error="ClientAuthenticationError"),
            AuthReplayProbe("httpx_after_rotate", True, False, error="ClientAuthenticationError"),
            AuthReplayProbe("httpx_fresh", True, False, error="ClientAuthenticationError"),
            AuthReplayProbe("cdp_in_page", True, True, notebook_count=3),
        ],
    )

    assert report.verdict == "browser_bound_replay"
    assert "issue #248" in report.recommendation


def test_auth_replay_classifies_stale_cookies():
    """Expired saved cookies should not be misdiagnosed as browser-bound replay.

    Regression test for issue #248 (leomesheti-crypto): httpx_saved and
    httpx_after_rotate both fail against dead on-disk cookies, and cdp_in_page
    passes because it runs inside a live, logged-in browser. Without a probe
    of fresh cookies retried through httpx, this pattern is indistinguishable
    from genuine device-bound replay. httpx_fresh disambiguates it: if a
    freshly re-extracted cookie jar succeeds through plain httpx, the saved
    cookies were simply stale.
    """
    report = _classify_auth_replay(
        "default",
        [
            AuthReplayProbe("httpx_saved", True, False, error="ClientAuthenticationError"),
            AuthReplayProbe("httpx_after_rotate", True, False, error="ClientAuthenticationError"),
            AuthReplayProbe("httpx_fresh", True, True, notebook_count=75),
            AuthReplayProbe("cdp_in_page", True, True, notebook_count=75),
        ],
    )

    assert report.verdict == "stale_cookies"
    assert "nlm login" in report.recommendation
    assert "NOTEBOOKLM_RPC_TRANSPORT" not in report.recommendation
    assert "device" in report.recommendation.lower() or "binding" in report.recommendation.lower()


def test_auth_replay_classifies_browser_bound_replay_when_fresh_httpx_also_fails():
    """Genuine device binding: even freshly re-extracted cookies fail outside the browser."""
    report = _classify_auth_replay(
        "default",
        [
            AuthReplayProbe("httpx_saved", True, False, error="ClientAuthenticationError"),
            AuthReplayProbe("httpx_after_rotate", True, False, error="ClientAuthenticationError"),
            AuthReplayProbe("httpx_fresh", True, False, error="ClientAuthenticationError"),
            AuthReplayProbe("cdp_in_page", True, True, notebook_count=3),
        ],
    )

    assert report.verdict == "browser_bound_replay"
    assert "issue #248" in report.recommendation


def test_auth_replay_classifies_cdp_skipped():
    report = _classify_auth_replay(
        "default",
        [
            AuthReplayProbe("httpx_saved", True, False, error="ClientAuthenticationError"),
            AuthReplayProbe("httpx_after_rotate", True, False, error="ClientAuthenticationError"),
            AuthReplayProbe("cdp_in_page", False, False, detail="No profile"),
        ],
    )

    assert report.verdict == "httpx_failed_cdp_skipped"
    assert "CDP" in report.recommendation


def test_diagnostic_rpc_headers_match_notebooklm_client_requirements():
    class Parser:
        csrf_token = "csrf"

        @staticmethod
        def _get_base_url():
            return "https://notebooklm.google.com"

    headers = _diagnostic_rpc_headers(Parser())

    assert headers["Content-Type"] == "application/x-www-form-urlencoded;charset=UTF-8"
    assert headers["Origin"] == "https://notebooklm.google.com"
    assert headers["Referer"] == "https://notebooklm.google.com/"
    assert headers["X-Same-Domain"] == "1"
    assert headers["X-Goog-Csrf-Token"] == "csrf"
    assert "User-Agent" in headers
