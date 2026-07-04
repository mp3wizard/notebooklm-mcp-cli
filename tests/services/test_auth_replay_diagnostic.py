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
