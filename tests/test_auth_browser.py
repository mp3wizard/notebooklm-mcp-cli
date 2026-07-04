"""Tests for supported authentication browser behavior."""

import json
from unittest.mock import patch


def test_select_auth_backend_ignores_firefox_preference_and_uses_chromium():
    from notebooklm_tools.utils.auth_browser import select_auth_backend

    with (
        patch("notebooklm_tools.utils.cdp._get_chromium_path", return_value="chromium"),
        patch("notebooklm_tools.utils.cdp.get_browser_display_name", return_value="Chromium"),
    ):
        backend = select_auth_backend("firefox")

    assert backend == {"backend": "chromium_cdp", "browser": "Chromium"}


def test_select_auth_backend_auto_prefers_chromium_when_available():
    from notebooklm_tools.utils.auth_browser import select_auth_backend

    with (
        patch("notebooklm_tools.utils.cdp._get_chromium_path", return_value="google-chrome"),
        patch("notebooklm_tools.utils.cdp.get_browser_display_name", return_value="Google Chrome"),
    ):
        backend = select_auth_backend("auto")

    assert backend == {"backend": "chromium_cdp", "browser": "Google Chrome"}


def test_select_auth_backend_returns_none_when_no_chromium_browser_available():
    from notebooklm_tools.utils.auth_browser import select_auth_backend

    with patch("notebooklm_tools.utils.cdp._get_chromium_path", return_value=None):
        backend = select_auth_backend("auto")

    assert backend is None


def test_supported_auth_browsers_excludes_firefox():
    from notebooklm_tools.utils.auth_browser import get_supported_auth_browsers

    with patch(
        "notebooklm_tools.utils.cdp.get_supported_browsers",
        return_value=["Google Chrome", "Chromium"],
    ):
        browsers = get_supported_auth_browsers()

    assert browsers == ["Google Chrome", "Chromium"]


def test_get_chromium_path_ignores_explicit_firefox_preference():
    from notebooklm_tools.utils.cdp import _get_chromium_path

    assert _get_chromium_path("firefox") is None


def test_saved_legacy_browser_backend_is_read_from_metadata(tmp_path, monkeypatch):
    from notebooklm_tools.core.auth import AuthManager
    from notebooklm_tools.utils.auth_browser import _get_saved_browser_backend

    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path))

    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "sid", "HSID": "hsid"}, email="user@example.com")

    metadata = json.loads(auth.metadata_file.read_text(encoding="utf-8"))
    metadata["browser_backend"] = "firefox_playwright"
    auth.metadata_file.write_text(json.dumps(metadata), encoding="utf-8")

    assert _get_saved_browser_backend("default") == "firefox_playwright"


def test_flatten_cookies_prefers_google_com_over_other_domains():
    from notebooklm_tools.utils.browser import flatten_cookies

    cookies = [
        {"name": "SID", "value": "youtube_sid", "domain": ".youtube.com"},
        {"name": "SID", "value": "google_sid", "domain": ".google.com"},
        {"name": "SID", "value": "vn_sid", "domain": ".google.com.vn"},
        {"name": "HSID", "value": "youtube_hsid", "domain": ".youtube.com"},
        {"name": "HSID", "value": "google_hsid", "domain": ".google.com"},
        {"name": "ONLY_VN", "value": "vn_only", "domain": ".google.com.vn"},
    ]

    flat = flatten_cookies(cookies)

    assert flat["SID"] == "google_sid"
    assert flat["HSID"] == "google_hsid"
    assert flat["ONLY_VN"] == "vn_only"


def test_flatten_cookies_passthrough_dict_and_skips_malformed():
    from notebooklm_tools.utils.browser import flatten_cookies

    assert flatten_cookies({"SID": "x"}) == {"SID": "x"}
    assert flatten_cookies([{"name": "SID"}, {"value": "no_name"}]) == {}


def test_flatten_cookies_empty_list_and_empty_value():
    from notebooklm_tools.utils.browser import flatten_cookies

    assert flatten_cookies([]) == {}
    assert flatten_cookies([{"name": "X", "value": ""}]) == {"X": ""}


def test_validate_cookies_accepts_chrome_list():
    from notebooklm_tools.core.auth import validate_cookies

    chrome_list = [
        {"name": n, "value": "v", "domain": ".google.com"}
        for n in ("SID", "HSID", "SSID", "APISID", "SAPISID")
    ]

    assert validate_cookies(chrome_list) is True
    assert validate_cookies(chrome_list[:2]) is False


def test_validate_notebooklm_cookies_accepts_chrome_list():
    from notebooklm_tools.utils.browser import validate_notebooklm_cookies

    chrome_list = [
        {"name": "SID", "value": "v", "domain": ".google.com"},
        {"name": "HSID", "value": "v", "domain": ".google.com"},
    ]

    assert validate_notebooklm_cookies(chrome_list) is True
    assert validate_notebooklm_cookies([]) is False


def test_auth_tokens_cookie_header_flattens_list():
    from notebooklm_tools.core.auth import AuthTokens

    tokens = AuthTokens(
        cookies=[
            {"name": "SID", "value": "vn", "domain": ".google.com.vn"},
            {"name": "SID", "value": "google", "domain": ".google.com"},
        ]
    )

    assert tokens.cookie_header == "SID=google"


def test_get_headers_flattens_list_cookies(tmp_path, monkeypatch):
    from notebooklm_tools.core.auth import AuthManager

    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path))

    auth = AuthManager("default")
    auth.save_profile(
        cookies=[
            {"name": "SID", "value": "google", "domain": ".google.com"},
            {"name": "SID", "value": "youtube", "domain": ".youtube.com"},
        ],
        csrf_token="csrf1",
        email="u@example.com",
    )

    headers = auth.get_headers()

    assert "SID=google" in headers["Cookie"]
    assert "youtube" not in headers["Cookie"]
    assert headers["X-Goog-Csrf-Token"] == "csrf1"
