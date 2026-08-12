"""Regression tests for manual-login host detection (issue #292)."""

from types import SimpleNamespace

import pytest

from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.core.exceptions import AuthenticationError


@pytest.fixture
def cookie_file(tmp_path):
    path = tmp_path / "cookies.txt"
    path.write_text("SID=sid; HSID=hsid", encoding="utf-8")
    return path


@pytest.fixture
def auth_manager(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "notebooklm_tools.utils.config.get_profile_dir",
        lambda name: tmp_path / "profiles" / name,
    )
    return AuthManager("manual-test")


def test_manual_login_persists_rebrand_host(auth_manager, cookie_file, monkeypatch):
    monkeypatch.delenv("NOTEBOOKLM_BASE_URL", raising=False)

    def fetch_homepage(cookies, *, timeout=12.0, base_url=None):
        if base_url == "https://notebooklm.google.com":
            return SimpleNamespace(status_code=200, url="https://accounts.google.com/login")
        return SimpleNamespace(status_code=200, url="https://notebook.google.com/")

    monkeypatch.setattr(
        "notebooklm_tools.core.auth._fetch_notebooklm_homepage",
        fetch_homepage,
    )

    auth_manager.login_with_file(cookie_file)

    assert auth_manager.load_profile(force_reload=True).base_host == "notebook.google.com"


def test_manual_login_preserves_legacy_host(auth_manager, cookie_file, monkeypatch):
    monkeypatch.delenv("NOTEBOOKLM_BASE_URL", raising=False)
    monkeypatch.setattr(
        "notebooklm_tools.core.auth._fetch_notebooklm_homepage",
        lambda cookies, *, timeout=12.0, base_url=None: SimpleNamespace(
            status_code=200,
            url="https://notebooklm.google.com/",
        ),
    )

    auth_manager.login_with_file(cookie_file)

    assert auth_manager.load_profile(force_reload=True).base_host == "notebooklm.google.com"


def test_manual_login_rejects_cookies_that_fail_on_both_hosts(
    auth_manager, cookie_file, monkeypatch
):
    monkeypatch.delenv("NOTEBOOKLM_BASE_URL", raising=False)
    monkeypatch.setattr(
        "notebooklm_tools.core.auth._fetch_notebooklm_homepage",
        lambda cookies, *, timeout=12.0, base_url=None: SimpleNamespace(
            status_code=200,
            url="https://accounts.google.com/login",
        ),
    )

    with pytest.raises(AuthenticationError, match="rejected"):
        auth_manager.login_with_file(cookie_file)

    assert not auth_manager.profile_exists()


def test_manual_login_honors_explicit_base_url(auth_manager, cookie_file, monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_BASE_URL", "https://notebook.cloud.google.com")

    def fetch_homepage(cookies, *, timeout=12.0, base_url=None):
        if base_url != "https://notebook.cloud.google.com":
            raise AssertionError(f"unexpected base URL: {base_url}")
        return SimpleNamespace(status_code=200, url="https://notebook.cloud.google.com/")

    monkeypatch.setattr(
        "notebooklm_tools.core.auth._fetch_notebooklm_homepage",
        fetch_homepage,
    )

    auth_manager.login_with_file(cookie_file)

    assert auth_manager.load_profile(force_reload=True).base_host == "notebook.cloud.google.com"


def test_manual_login_reports_probe_network_failure(auth_manager, cookie_file, monkeypatch):
    monkeypatch.delenv("NOTEBOOKLM_BASE_URL", raising=False)

    def fail_fetch(cookies, *, timeout=12.0, base_url=None):
        raise TimeoutError("timed out")

    monkeypatch.setattr(
        "notebooklm_tools.core.auth._fetch_notebooklm_homepage",
        fail_fetch,
    )

    with pytest.raises(AuthenticationError, match="Could not reach"):
        auth_manager.login_with_file(cookie_file)

    assert not auth_manager.profile_exists()
