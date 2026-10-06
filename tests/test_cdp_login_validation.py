from unittest.mock import patch

import httpx
import pytest
from typer.testing import CliRunner

from notebooklm_tools.cli.main import app
from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.core.errors import ClientAuthenticationError
from notebooklm_tools.core.exceptions import AuthenticationError
from notebooklm_tools.utils import cdp

ANONYMOUS_HTML = '{"FdrFJe":"123","cfb2h":"public-build"}'
AUTHENTICATED_HTML = '{"SNlM0e":"real-csrf","FdrFJe":"456","cfb2h":"app-build"}'
AUTHENTICATED_COOKIES = [
    {"name": name, "value": "signed-in", "domain": ".google.com", "path": "/"}
    for name in ("SID", "HSID", "SSID", "APISID", "SAPISID")
]
ANONYMOUS_COOKIES = [{"name": "NID", "value": "anonymous", "domain": ".google.com", "path": "/"}]


@pytest.fixture
def browser(monkeypatch):
    state = {"elapsed": 0.0, "signed_in_after": float("inf")}
    monkeypatch.setattr(cdp.time, "time", lambda: state["elapsed"])
    monkeypatch.setattr(
        cdp.time, "sleep", lambda seconds: state.update(elapsed=state["elapsed"] + seconds)
    )
    monkeypatch.setattr(
        cdp,
        "find_or_create_notebooklm_page_by_cdp_url",
        lambda url: {"url": "https://notebook.google.com/", "webSocketDebuggerUrl": "ws://page"},
    )
    monkeypatch.setattr(cdp, "get_current_url", lambda ws: "https://notebook.google.com/")
    monkeypatch.setattr(
        cdp,
        "get_page_html",
        lambda ws: (
            AUTHENTICATED_HTML if state["elapsed"] >= state["signed_in_after"] else ANONYMOUS_HTML
        ),
    )
    monkeypatch.setattr(
        cdp,
        "get_page_cookies",
        lambda ws: (
            AUTHENTICATED_COOKIES
            if state["elapsed"] >= state["signed_in_after"]
            else ANONYMOUS_COOKIES
        ),
    )
    return state


def test_login_waits_through_anonymous_landing_page(browser):
    browser["signed_in_after"] = 1.0

    result = cdp.extract_cookies_from_page("http://127.0.0.1:9223", login_timeout=3)

    assert result["csrf_token"] == "real-csrf"
    assert result["session_id"] == "456"
    assert result["cookies"] == AUTHENTICATED_COOKIES
    assert result["base_host"] == "notebook.google.com"


def test_anonymous_landing_page_times_out_instead_of_returning_credentials(browser):
    with pytest.raises(AuthenticationError):
        cdp.extract_cookies_from_page("http://127.0.0.1:9223", login_timeout=2)


def test_noninteractive_extraction_rejects_anonymous_landing_page(browser):
    with pytest.raises(AuthenticationError):
        cdp.extract_cookies_from_page("http://127.0.0.1:9223", wait_for_login=False)


@pytest.mark.parametrize("missing", ["csrf", "cookies"])
def test_incomplete_sign_in_is_not_accepted(browser, monkeypatch, missing):
    browser["signed_in_after"] = 0
    if missing == "csrf":
        monkeypatch.setattr(cdp, "get_page_html", lambda ws: ANONYMOUS_HTML)
    else:
        monkeypatch.setattr(cdp, "get_page_cookies", lambda ws: ANONYMOUS_COOKIES)
    with pytest.raises(AuthenticationError):
        cdp.extract_cookies_from_page("http://127.0.0.1:9223", login_timeout=2)


@pytest.mark.parametrize("saved", [False, True])
def test_cli_does_not_save_anonymous_browser_credentials(browser, monkeypatch, saved):
    if saved:
        AuthManager("content-work").save_profile(cookies={"NID": "existing-anonymous"})
    monkeypatch.setattr(cdp, "get_chrome_path", lambda: "chrome")
    monkeypatch.setattr(
        "notebooklm_tools.utils.config.check_migration_sources",
        lambda: {"chrome_profiles": []},
    )
    monkeypatch.setattr(cdp, "terminate_chrome", lambda **kwargs: True)
    monkeypatch.setattr(
        cdp,
        "extract_cookies_via_cdp",
        lambda **kwargs: cdp.extract_cookies_from_page("http://127.0.0.1:9223", login_timeout=2),
    )
    response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://notebook.google.com/"),
        text=ANONYMOUS_HTML,
    )
    with (
        patch("notebooklm_tools.core.auth._fetch_notebooklm_homepage", return_value=response),
        patch("notebooklm_tools.core.client.NotebookLMClient") as client,
    ):
        client.return_value.list_notebooks.side_effect = ClientAuthenticationError("expired")
        result = CliRunner().invoke(
            app, ["login", "--profile", "content-work", "--storage", "file"]
        )

    assert result.exit_code == 1
    assert "Login timeout" in result.output
    assert "Successfully authenticated" not in result.output
    assert "Authentication valid" not in result.output
    if saved:
        assert AuthManager("content-work").load_profile().cookies == {"NID": "existing-anonymous"}
    else:
        assert not AuthManager("content-work").profile_exists()
