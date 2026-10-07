from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from notebooklm_tools.cli.main import app


@pytest.mark.parametrize("error_kind", ["client", "auth"])
def test_notebook_count_does_not_hide_authentication_rejection(monkeypatch, error_kind):
    from notebooklm_tools.cli.main import _best_effort_notebook_count
    from notebooklm_tools.core.errors import ClientAuthenticationError
    from notebooklm_tools.core.exceptions import AuthenticationError

    error = ClientAuthenticationError if error_kind == "client" else AuthenticationError

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def list_notebooks(self):
            raise error("Authentication expired")

    monkeypatch.setattr("notebooklm_tools.core.client.NotebookLMClient", Client)
    profile = SimpleNamespace(
        cookies={"SID": "expired"},
        csrf_token="csrf",
        session_id="123",
        build_label="build",
        base_host="",
    )
    with pytest.raises(AuthenticationError):
        _best_effort_notebook_count(profile)


class FakeAuthManager:
    def __init__(self, profile_name: str):
        self.profile_name = profile_name
        self.profile_dir = f"/tmp/{profile_name}"  # nosec B108 - mock return value in test double, not a real filesystem path
        self.saved = None

    def load_profile(self):
        return SimpleNamespace(name=self.profile_name, email="user@example.com")

    def profile_exists(self):
        return True

    def save_profile(self, **kwargs):
        self.saved = kwargs


def test_login_uses_valid_saved_profile_without_opening_browser(monkeypatch):
    validate_calls = []

    def fake_validate(auth):
        validate_calls.append(auth.profile_name)
        return SimpleNamespace(name=auth.profile_name, email="user@example.com"), 3

    def fail_browser(*args, **kwargs):
        raise AssertionError("browser auth should not run when saved credentials are valid")

    monkeypatch.setattr("notebooklm_tools.core.auth.AuthManager", FakeAuthManager)
    monkeypatch.setattr("notebooklm_tools.cli.main._validate_saved_profile", fake_validate)
    monkeypatch.setattr("notebooklm_tools.utils.cdp.extract_cookies_via_cdp", fail_browser)

    result = CliRunner().invoke(app, ["login", "--profile", "KS"])

    assert result.exit_code == 0
    assert validate_calls == ["KS"]
    assert "Authentication valid!" in result.output
    assert "Notebooks found: 3" in result.output


def test_login_force_bypasses_saved_profile_validation(monkeypatch, tmp_path):
    validate_calls = []
    save_calls = []

    class SavingAuthManager(FakeAuthManager):
        def save_profile(self, **kwargs):
            save_calls.append(kwargs)

    def fake_validate(auth):
        validate_calls.append(auth.profile_name)
        return SimpleNamespace(name=auth.profile_name, email="user@example.com"), 3

    monkeypatch.setattr("notebooklm_tools.core.auth.AuthManager", SavingAuthManager)
    monkeypatch.setattr("notebooklm_tools.cli.main._validate_saved_profile", fake_validate)
    monkeypatch.setattr("notebooklm_tools.utils.cdp.get_chrome_path", lambda: "chrome")
    monkeypatch.setattr("notebooklm_tools.utils.cdp.get_browser_display_name", lambda: "Chrome")
    monkeypatch.setattr("notebooklm_tools.utils.cdp.terminate_chrome", lambda: True)
    monkeypatch.setattr(
        "notebooklm_tools.utils.cdp.extract_cookies_via_cdp",
        lambda **kwargs: {
            "cookies": {"SID": "sid"},
            "csrf_token": "csrf",
            "session_id": "session",
            "email": "user@example.com",
            "build_label": "build",
        },
    )
    monkeypatch.setattr("notebooklm_tools.utils.config.get_storage_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "notebooklm_tools.utils.config.check_migration_sources",
        lambda: {"chrome_profiles": []},
    )

    result = CliRunner().invoke(app, ["login", "--profile", "KS", "--force"])

    assert result.exit_code == 0
    assert validate_calls == []
    assert save_calls == [
        {
            "cookies": {"SID": "sid"},
            "csrf_token": "csrf",
            "session_id": "session",
            "email": "user@example.com",
            "force": True,
            "build_label": "build",
            "base_host": "",
            "browser_backend": "chromium_cdp",
        }
    ]
    assert "Successfully authenticated!" in result.output


def test_login_clear_bypasses_valid_saved_profile(monkeypatch, tmp_path):
    """--clear must reach the browser even when the saved session still validates.

    Otherwise the early "already valid" return skips the profile wipe, so
    switching accounts silently does nothing (issue #330).
    """
    validate_calls = []
    extract_kwargs = {}

    def fake_validate(auth):
        validate_calls.append(auth.profile_name)
        return SimpleNamespace(name=auth.profile_name, email="user@example.com"), 3

    def fake_extract(**kwargs):
        extract_kwargs.update(kwargs)
        return {
            "cookies": {"SID": "sid"},
            "csrf_token": "csrf",
            "session_id": "session",
            "email": "user@example.com",
            "build_label": "build",
        }

    monkeypatch.setattr("notebooklm_tools.core.auth.AuthManager", FakeAuthManager)
    monkeypatch.setattr("notebooklm_tools.cli.main._validate_saved_profile", fake_validate)
    monkeypatch.setattr("notebooklm_tools.utils.cdp.get_chrome_path", lambda: "chrome")
    monkeypatch.setattr("notebooklm_tools.utils.cdp.get_browser_display_name", lambda: "Chrome")
    monkeypatch.setattr("notebooklm_tools.utils.cdp.terminate_chrome", lambda: True)
    monkeypatch.setattr("notebooklm_tools.utils.cdp.extract_cookies_via_cdp", fake_extract)
    monkeypatch.setattr("notebooklm_tools.utils.config.get_storage_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "notebooklm_tools.utils.config.check_migration_sources",
        lambda: {"chrome_profiles": []},
    )

    result = CliRunner().invoke(app, ["login", "--profile", "KS", "--clear"])

    assert result.exit_code == 0
    assert validate_calls == []
    assert extract_kwargs.get("clear_profile") is True
    assert "Successfully authenticated!" in result.output


class CheckAuthManager(FakeAuthManager):
    """AuthManager whose check_validity returns a preconfigured result."""

    result = None  # set per-test before invoking the CLI

    def load_profile(self):
        return SimpleNamespace(
            name=self.profile_name,
            email="user@example.com",
            cookies={"SID": "sid"},
            csrf_token="csrf",
            session_id="session",
            build_label="build",
        )

    def check_validity(self, *, live: bool = True, timeout: float = 12.0):
        return CheckAuthManager.result


def test_validate_saved_profile_uses_api_aware_auth_policy(monkeypatch):
    from notebooklm_tools.cli.main import _validate_saved_profile

    calls = []

    def fake_usable(**kwargs):
        calls.append(kwargs)
        return True, "configured", None

    monkeypatch.setattr(
        "notebooklm_tools.services.auth.credentials_are_usable",
        fake_usable,
    )
    monkeypatch.setattr(
        "notebooklm_tools.cli.main._best_effort_notebook_count",
        lambda profile: 7,
    )

    profile, count = _validate_saved_profile(CheckAuthManager("KS"))

    assert profile.name == "KS"
    assert count == 7
    assert calls == [{"force": True, "profile": "KS"}]


def test_validate_saved_profile_rejects_rpc_stale_false_positive(monkeypatch):
    from notebooklm_tools.cli.main import _validate_saved_profile
    from notebooklm_tools.core.exceptions import AuthenticationError

    monkeypatch.setattr(
        "notebooklm_tools.services.auth.credentials_are_usable",
        lambda **_kwargs: (False, "stale", "NotebookLM RPC rejected the session"),
    )
    monkeypatch.setattr(
        "notebooklm_tools.cli.main._best_effort_notebook_count",
        lambda _profile: (_ for _ in ()).throw(
            AssertionError("count must not run for stale credentials")
        ),
    )

    with pytest.raises(AuthenticationError, match="expired"):
        _validate_saved_profile(CheckAuthManager("KS"))


def test_validate_saved_profile_avoids_duplicate_notebook_count_rpc(tmp_path, monkeypatch):
    """A valid live check should reuse the confirmed count without a 2nd list_notebooks RPC."""
    import notebooklm_tools.services.auth as sa
    from notebooklm_tools.cli.main import _validate_saved_profile
    from notebooklm_tools.core.auth import AuthManager

    monkeypatch.setattr("notebooklm_tools.utils.config.get_storage_dir", lambda: tmp_path)
    mgr = AuthManager("test_reuse")
    mgr.save_profile(cookies={"SID": "s"}, csrf_token="c", session_id="1", build_label="b")

    call_count = 0

    class CountingClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def list_notebooks(self):
            nonlocal call_count
            call_count += 1
            return ["nb1", "nb2"]

    monkeypatch.setattr("notebooklm_tools.core.client.NotebookLMClient", CountingClient)
    monkeypatch.setattr(
        sa.AuthHealthChecker,
        "_probe_homepage",
        lambda *a, **k: (True, None, "c", 200),
    )

    profile, count = _validate_saved_profile(mgr)

    assert profile.name == "test_reuse"
    assert count == 2
    assert call_count == 1


def test_check_valid_reports_notebook_count(monkeypatch):
    monkeypatch.setattr("notebooklm_tools.core.auth.AuthManager", CheckAuthManager)
    monkeypatch.setattr(
        "notebooklm_tools.services.auth.credentials_are_usable",
        lambda **_kwargs: (True, "configured", None),
    )
    monkeypatch.setattr("notebooklm_tools.cli.main._best_effort_notebook_count", lambda profile: 5)

    result = CliRunner().invoke(app, ["login", "--check", "--profile", "KS"])

    assert result.exit_code == 0
    assert "Authentication valid!" in result.output
    assert "Notebooks found: 5" in result.output


def test_check_valid_when_notebook_count_unavailable_does_not_fail(monkeypatch):
    """The reported bug: a slow/timed-out notebook list must not fail a valid check."""
    monkeypatch.setattr("notebooklm_tools.core.auth.AuthManager", CheckAuthManager)
    monkeypatch.setattr(
        "notebooklm_tools.services.auth.credentials_are_usable",
        lambda **_kwargs: (True, "configured", None),
    )
    # Simulate list_notebooks timing out → best-effort count degrades to None
    monkeypatch.setattr(
        "notebooklm_tools.cli.main._best_effort_notebook_count", lambda profile: None
    )

    result = CliRunner().invoke(app, ["login", "--check", "--profile", "KS"])

    assert result.exit_code == 0
    assert "Authentication valid!" in result.output
    assert "Notebook count unavailable" in result.output


def test_check_invalid_credentials_exit_2(monkeypatch):
    monkeypatch.setattr("notebooklm_tools.core.auth.AuthManager", CheckAuthManager)
    monkeypatch.setattr(
        "notebooklm_tools.services.auth.credentials_are_usable",
        lambda **_kwargs: (False, "stale", "NotebookLM RPC rejected the session"),
    )

    def fail_count(profile):
        raise AssertionError("notebook count must not be fetched for invalid auth")

    monkeypatch.setattr("notebooklm_tools.cli.main._best_effort_notebook_count", fail_count)

    result = CliRunner().invoke(app, ["login", "--check", "--profile", "KS"])

    assert result.exit_code == 2
    assert "Authentication failed" in result.output


def test_best_effort_notebook_count_swallows_timeout(monkeypatch):
    """_best_effort_notebook_count returns None instead of raising on a read timeout."""
    import httpx

    from notebooklm_tools.cli.main import _best_effort_notebook_count

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def list_notebooks(self):
            raise httpx.ReadTimeout("read timed out")

    monkeypatch.setattr("notebooklm_tools.core.client.NotebookLMClient", FakeClient)
    profile = SimpleNamespace(
        cookies={"SID": "sid"},
        csrf_token="csrf",
        session_id="session",
        build_label="build",
        base_host="",
    )

    assert _best_effort_notebook_count(profile) is None


def test_best_effort_notebook_count_returns_count(monkeypatch):
    from notebooklm_tools.cli.main import _best_effort_notebook_count

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def list_notebooks(self):
            return ["nb1", "nb2", "nb3"]

    monkeypatch.setattr("notebooklm_tools.core.client.NotebookLMClient", FakeClient)
    profile = SimpleNamespace(
        cookies={"SID": "sid"},
        csrf_token="csrf",
        session_id="session",
        build_label="build",
        base_host="",
    )

    assert _best_effort_notebook_count(profile) == 3


def test_best_effort_notebook_count_swallows_non_timeout_error(monkeypatch):
    """Any error (not just a timeout) from the count call degrades to None."""
    from notebooklm_tools.cli.main import _best_effort_notebook_count

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def list_notebooks(self):
            raise ValueError("malformed batchexecute response")

    monkeypatch.setattr("notebooklm_tools.core.client.NotebookLMClient", FakeClient)
    profile = SimpleNamespace(
        cookies={"SID": "sid"}, csrf_token="csrf", session_id="session", build_label="build"
    )

    assert _best_effort_notebook_count(profile) is None


def test_auth_failure_network_error_keeps_credentials_hint():
    """A homepage-probe network blip must not tell the user to re-login; it
    must signal the credentials may still be valid (the heart of the bug)."""
    from notebooklm_tools.cli.main import _auth_failure_from_result

    exc = _auth_failure_from_result(SimpleNamespace(reason="network_error: ReadTimeout"))

    assert "Could not reach NotebookLM" in exc.message
    assert "may still be valid" in (exc.hint or "")


def test_auth_failure_no_tokens_prompts_login():
    from notebooklm_tools.cli.main import _auth_failure_from_result

    exc = _auth_failure_from_result(SimpleNamespace(reason="no_tokens"))

    assert "No saved credentials" in exc.message
    assert "nlm login" in (exc.hint or "")


def test_check_network_error_exits_2_without_crashing(monkeypatch):
    """An unverified auth state fails cleanly without forcing a re-login claim."""
    monkeypatch.setattr("notebooklm_tools.core.auth.AuthManager", CheckAuthManager)
    monkeypatch.setattr(
        "notebooklm_tools.services.auth.credentials_are_usable",
        lambda **_kwargs: (False, "unverified", "ReadTimeout"),
    )

    def fail_count(profile):
        raise AssertionError("notebook count must not be fetched when the probe failed")

    monkeypatch.setattr("notebooklm_tools.cli.main._best_effort_notebook_count", fail_count)

    result = CliRunner().invoke(app, ["login", "--check", "--profile", "KS"])

    assert result.exit_code == 2
    assert "may still be valid" in result.output
