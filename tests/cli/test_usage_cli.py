"""CLI tests for profile-aware plan usage reporting."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from notebooklm_tools.cli.main import app

runner = CliRunner()
_USAGE = {
    "windows": [
        {
            "window": "rolling",
            "percent_used": 10.0,
            "percent_remaining": 90.0,
            "resets_at": "2026-09-13T06:00:00+00:00",
        }
    ],
    "tier": "NOTEBOOKLM_TIER_PRO_CONSUMER_USER",
}


def _invoke_profile(option: str, profile: str = "secondary"):
    client = MagicMock(name=f"client-{profile}")
    with (
        patch("notebooklm_tools.cli.commands.usage.get_client", return_value=client) as get_client,
        patch(
            "notebooklm_tools.cli.commands.usage.usage_service.get_usage", return_value=_USAGE
        ) as get_usage,
    ):
        result = runner.invoke(app, ["usage", option, profile, "--json"])
    return result, client, get_client, get_usage


def test_usage_accepts_long_profile_option():
    result, client, get_client, get_usage = _invoke_profile("--profile")

    assert result.exit_code == 0
    get_client.assert_called_once_with("secondary")
    get_usage.assert_called_once_with(client)
    assert '"tier": "NOTEBOOKLM_TIER_PRO_CONSUMER_USER"' in result.stdout


def test_usage_accepts_short_profile_option():
    result, client, get_client, get_usage = _invoke_profile("-p")

    assert result.exit_code == 0
    get_client.assert_called_once_with("secondary")
    get_usage.assert_called_once_with(client)


def test_usage_without_profile_keeps_default_client_behavior():
    client = MagicMock(name="default-client")
    with (
        patch("notebooklm_tools.cli.commands.usage.get_client", return_value=client) as get_client,
        patch("notebooklm_tools.cli.commands.usage.usage_service.get_usage", return_value=_USAGE),
    ):
        result = runner.invoke(app, ["usage", "--json"])

    assert result.exit_code == 0
    get_client.assert_called_once_with()


def test_usage_missing_profile_uses_normal_cli_error():
    result = runner.invoke(app, ["usage", "--profile", "does-not-exist"])

    assert result.exit_code == 1
    assert "Profile 'does-not-exist' not found" in result.stdout


def test_explicit_profile_overrides_environment_cookies(monkeypatch):
    from notebooklm_tools.services.auth import AuthManager

    AuthManager("work").save_profile(cookies={"SID": "work"}, csrf_token="work-csrf")
    monkeypatch.setenv("NOTEBOOKLM_COOKIES", "SID=personal")
    with (
        patch("notebooklm_tools.cli.utils.NotebookLMClient") as client_type,
        patch("notebooklm_tools.cli.commands.usage.usage_service.get_usage", return_value=_USAGE),
    ):
        result = runner.invoke(app, ["usage", "--profile", "work", "--json"])
    assert result.exit_code == 0
    assert client_type.call_args.kwargs["cookies"] == {"SID": "work"}
    assert client_type.call_args.kwargs["profile_name"] == "work"


def test_missing_explicit_profile_does_not_fall_back_to_environment(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_COOKIES", "SID=personal")
    with patch("notebooklm_tools.cli.utils.NotebookLMClient") as client_type:
        result = runner.invoke(app, ["usage", "--profile", "missing"])
    assert result.exit_code == 1
    assert "Profile 'missing' not found" in result.stdout
    client_type.assert_not_called()


def test_no_profile_keeps_environment_auth(monkeypatch):
    from notebooklm_tools.cli.utils import get_client

    monkeypatch.setenv("NOTEBOOKLM_COOKIES", "SID=personal")
    with patch("notebooklm_tools.cli.utils.NotebookLMClient") as client_type:
        get_client()
    client_type.assert_called_once_with(cookies={"SID": "personal"})
