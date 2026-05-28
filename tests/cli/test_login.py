from types import SimpleNamespace

from typer.testing import CliRunner

from notebooklm_tools.cli.main import app


class FakeAuthManager:
    def __init__(self, profile_name: str):
        self.profile_name = profile_name
        self.profile_dir = f"/tmp/{profile_name}"
        self.saved = None

    def load_profile(self):
        return SimpleNamespace(name=self.profile_name, email="user@example.com")

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
        }
    ]
    assert "Successfully authenticated!" in result.output
