"""Tests for CLI one-time storage notice and probe performance guard."""

import pytest
from typer.testing import CliRunner

from notebooklm_tools.cli.main import app
from notebooklm_tools.cli.utils import print_storage_mode_notification
from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.core.credential_backend_worker import CredentialWorkerClient
from notebooklm_tools.core.notices import is_cli_notice_shown
from notebooklm_tools.services.auth_storage import set_storage_mode
from notebooklm_tools.utils.config import reset_config

runner = CliRunner()


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch, fake_credential_store):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path))
    reset_config()
    yield
    reset_config()


def test_50_cli_commands_in_ssh_session_zero_probes(monkeypatch, fake_credential_store):
    """50 CLI commands in a simulated SSH session must perform 0 keystore probes."""
    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "test_sid"}, email="user@example.com")

    # Simulate SSH session
    monkeypatch.setenv("SSH_CONNECTION", "192.168.1.1 12345 192.168.1.2 22")

    probe_calls = 0
    orig_probe = CredentialWorkerClient.probe

    def _spy_probe(self, service, account):
        nonlocal probe_calls
        probe_calls += 1
        return orig_probe(self, service, account)

    monkeypatch.setattr(CredentialWorkerClient, "probe", _spy_probe)

    for _ in range(50):
        res = runner.invoke(app, ["auth", "storage", "status"])
        assert res.exit_code == 0
        assert "🔒 New" not in res.output

    assert probe_calls == 0


def test_cli_notice_appears_on_tty_when_eligible(
    monkeypatch, fake_credential_store, capsys, pretend_desktop
):
    """CLI notice displays once on TTY when keystore is available and profile is file mode."""
    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "test_sid"}, email="user@example.com")

    # Mock TTY as True
    import sys

    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    assert not is_cli_notice_shown()

    print_storage_mode_notification()
    captured = capsys.readouterr()
    assert (
        "🔒 New (optional): protect your saved login in your OS keystore → nlm auth storage set protected"
        in captured.err
    )
    assert captured.out == ""
    assert is_cli_notice_shown()

    # Second call must not print
    print_storage_mode_notification()
    captured2 = capsys.readouterr()
    assert "🔒 New" not in captured2.err


def test_cli_notice_omitted_on_non_tty(monkeypatch, fake_credential_store, capsys):
    """CLI notice is not shown when stdout/stderr are not TTYs."""
    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "test_sid"}, email="user@example.com")

    import sys

    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

    print_storage_mode_notification()
    captured = capsys.readouterr()
    assert "🔒 New" not in captured.out + captured.err
    assert not is_cli_notice_shown()


def test_cli_notice_omitted_when_already_protected(monkeypatch, fake_credential_store, capsys):
    """CLI notice is not shown if default profile is already in protected mode."""
    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "test_sid"}, email="user@example.com")
    set_storage_mode("protected", "default")

    import sys

    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    print_storage_mode_notification()
    captured = capsys.readouterr()
    assert "🔒 New" not in captured.out + captured.err
