"""Regression coverage for authentication issues #379, #380, and #381."""

import json

import pytest

from notebooklm_tools.core import auth
from notebooklm_tools.core.credential_store import StaleRevisionError
from notebooklm_tools.utils import cdp


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('"FdrFJe":"-221941101013684815"', "-221941101013684815"),
        ("f.sid=-7984489382980768703", "-7984489382980768703"),
        ('"FdrFJe":"123"', "123"),
        ("f.sid=123", "123"),
    ],
)
def test_session_ids(html, expected):
    assert cdp.extract_session_id(html) == expected
    assert auth.extract_session_id_from_page(html) == expected


@pytest.mark.parametrize("html", ['"FdrFJe":""', '"FdrFJe":"not-numeric"', "no session"])
def test_cdp_session_id_rejects_missing_or_nonnumeric_values(html):
    assert cdp.extract_session_id(html) == ""


def test_signed_out_http_200_is_auth_failure(tmp_path, monkeypatch):
    import httpx

    from notebooklm_tools.core.base import BaseClient

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url):
            return httpx.Response(
                200,
                text='<button class="landing-header-signin">Sign in</button>"FdrFJe":"-123"',
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(httpx, "Client", Client)
    monkeypatch.setattr(
        "notebooklm_tools.core.cookie_rotation.rotate_google_cookies", lambda *a, **kw: None
    )
    monkeypatch.setattr(BaseClient, "_get_httpx_cookies", lambda self: {})
    monkeypatch.setattr(BaseClient, "_is_enterprise", lambda self: False)
    monkeypatch.setattr("notebooklm_tools.utils.config.get_storage_dir", lambda: tmp_path)
    client = BaseClient.__new__(BaseClient)
    with pytest.raises(ValueError, match="Authentication expired"):
        client._refresh_auth_tokens()
    assert not (tmp_path / "debug_page.html").exists()


def test_stale_root_cannot_clobber_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path))
    from notebooklm_tools.utils import config

    monkeypatch.setattr(config, "get_base_default_profile", lambda: "default")
    fresh = auth.AuthTokens(cookies={"SID": "fresh"})
    stale = auth.AuthTokens(cookies={"SID": "stale"})
    auth.save_tokens_to_cache(fresh, profile_name="default", silent=True)
    auth._atomic_write_json(auth.get_cache_path(), stale.to_dict())
    with pytest.raises(StaleRevisionError):
        auth.save_tokens_to_cache(stale, profile_name="default", force=True)
    assert auth.get_auth_manager("default").load_profile(force_reload=True).cookies == fresh.cookies
    assert auth.load_cached_tokens("default").cookies == fresh.cookies
    # A genuinely new login must still replace both stores.
    newer = auth.AuthTokens(cookies={"SID": "new-login"})
    auth.save_tokens_to_cache(newer, profile_name="default", silent=True)
    assert json.loads(auth.get_cache_path().read_text())["cookies"] == newer.cookies
