"""Tests for supported authentication browser behavior."""

import json
from pathlib import Path
from unittest.mock import patch


def test_select_auth_backend_uses_firefox_when_explicitly_requested():
    from notebooklm_tools.utils.auth_browser import select_auth_backend

    with (
        patch("notebooklm_tools.utils.cdp._get_chromium_path", return_value="chromium"),
        patch("notebooklm_tools.utils.firefox.get_firefox_path", return_value="firefox"),
    ):
        backend = select_auth_backend("firefox")

    assert backend == {"backend": "firefox_profile", "browser": "Firefox"}


def test_select_auth_backend_auto_prefers_chromium_when_available():
    from notebooklm_tools.utils.auth_browser import select_auth_backend

    with (
        patch("notebooklm_tools.utils.cdp._get_chromium_path", return_value="google-chrome"),
        patch("notebooklm_tools.utils.cdp.get_browser_display_name", return_value="Google Chrome"),
        patch("notebooklm_tools.utils.firefox.get_firefox_path", return_value="firefox"),
    ):
        backend = select_auth_backend("auto")

    assert backend == {"backend": "chromium_cdp", "browser": "Google Chrome"}


def test_select_auth_backend_auto_uses_firefox_when_chromium_is_unavailable():
    from notebooklm_tools.utils.auth_browser import select_auth_backend

    with (
        patch("notebooklm_tools.utils.cdp._get_chromium_path", return_value=None),
        patch("notebooklm_tools.utils.firefox.get_firefox_path", return_value="firefox"),
    ):
        backend = select_auth_backend("auto")

    assert backend == {"backend": "firefox_profile", "browser": "Firefox"}


def test_supported_auth_browsers_includes_firefox_when_installed():
    from notebooklm_tools.utils.auth_browser import get_supported_auth_browsers

    with (
        patch(
            "notebooklm_tools.utils.cdp.get_supported_browsers",
            return_value=["Google Chrome", "Chromium"],
        ),
        patch("notebooklm_tools.utils.firefox.get_firefox_path", return_value="firefox"),
    ):
        browsers = get_supported_auth_browsers()

    assert browsers == ["Google Chrome", "Chromium", "Firefox"]


def test_get_chromium_path_ignores_explicit_firefox_preference():
    from notebooklm_tools.utils.cdp import _get_chromium_path

    assert _get_chromium_path("firefox") is None


def test_select_auth_backend_passes_comet_preference_to_chromium_discovery():
    from notebooklm_tools.utils.auth_browser import select_auth_backend

    with (
        patch(
            "notebooklm_tools.utils.cdp._get_chromium_path",
            return_value="/Applications/Comet.app/Contents/MacOS/Comet",
        ) as get_path,
        patch("notebooklm_tools.utils.cdp.get_browser_display_name", return_value="Comet"),
        patch("notebooklm_tools.utils.firefox.get_firefox_path", return_value=None),
    ):
        backend = select_auth_backend("comet")

    assert backend == {"backend": "chromium_cdp", "browser": "Comet"}
    get_path.assert_called_once_with("comet")


def test_get_chromium_path_selects_named_comet_on_macos():
    from notebooklm_tools.utils.cdp import _get_chromium_path

    expected = "/Applications/Comet.app/Contents/MacOS/Comet"

    def fake_exists(path: Path) -> bool:
        return str(path) == expected

    with (
        patch("notebooklm_tools.utils.cdp.platform.system", return_value="Darwin"),
        patch.object(Path, "exists", fake_exists),
        patch(
            "notebooklm_tools.utils.cdp._get_preferred_browser_path",
            return_value="",
            create=True,
        ),
    ):
        result = _get_chromium_path("comet")

    assert result == expected


def test_explicit_browser_path_wins_over_named_discovery(tmp_path):
    from notebooklm_tools.utils.cdp import _get_chromium_path

    executable = tmp_path / "future-browser"
    executable.write_text("browser", encoding="utf-8")
    executable.chmod(0o755)

    with (
        patch("notebooklm_tools.utils.cdp.platform.system", return_value="Linux"),
        patch("notebooklm_tools.utils.cdp.shutil.which", return_value="/usr/bin/google-chrome"),
        patch(
            "notebooklm_tools.utils.cdp._get_preferred_browser_path",
            return_value=str(executable),
            create=True,
        ),
    ):
        result = _get_chromium_path("chrome")

    assert result == str(executable)


def test_invalid_explicit_browser_path_does_not_fall_back(tmp_path):
    from notebooklm_tools.utils.cdp import _get_chromium_path

    missing = tmp_path / "missing-browser"

    with (
        patch("notebooklm_tools.utils.cdp.platform.system", return_value="Linux"),
        patch("notebooklm_tools.utils.cdp.shutil.which", return_value="/usr/bin/google-chrome"),
        patch(
            "notebooklm_tools.utils.cdp._get_preferred_browser_path",
            return_value=str(missing),
            create=True,
        ),
    ):
        result = _get_chromium_path("chrome")

    assert result is None


def test_invalid_explicit_browser_path_suppresses_firefox_fallback():
    from notebooklm_tools.utils.auth_browser import select_auth_backend

    with (
        patch("notebooklm_tools.utils.cdp._get_chromium_path", return_value=None),
        patch(
            "notebooklm_tools.utils.cdp._get_preferred_browser_path",
            return_value="/missing/browser",
            create=True,
        ),
        patch("notebooklm_tools.utils.firefox.get_firefox_path", return_value="/usr/bin/firefox"),
    ):
        backend = select_auth_backend("auto")

    assert backend is None


def test_browser_path_environment_override_is_loaded(monkeypatch, tmp_path):
    from notebooklm_tools.utils.config import load_config

    config_file = tmp_path / "missing-config.toml"
    monkeypatch.setenv("NLM_BROWSER_PATH", "/opt/custom/chromium")

    with patch("notebooklm_tools.utils.config.get_config_file", return_value=config_file):
        config = load_config()

    assert config.auth.browser_path == "/opt/custom/chromium"


def test_browser_path_is_serialized_to_toml():
    from notebooklm_tools.utils.config import AuthConfig, Config, _config_to_toml

    config = Config(auth=AuthConfig(browser_path="/opt/custom/chromium"))

    assert 'browser_path = "/opt/custom/chromium"' in _config_to_toml(config)


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
