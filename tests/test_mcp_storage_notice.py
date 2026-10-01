"""Tests for MCP response notice, zero-delay tool calls, and server_info wording."""

import time

import pytest

from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.core.credential_backend_worker import CredentialWorkerClient
from notebooklm_tools.mcp.tools._utils import (
    _mcp_probe_event,
    reset_mcp_probe_state,
    start_mcp_background_probe,
)
from notebooklm_tools.mcp.tools.server import server_info
from notebooklm_tools.services.auth_storage import set_storage_mode
from notebooklm_tools.utils.config import reset_config

EXPECTED_NOTICE = (
    "Tell the user once, in one short line: their saved Gemini Notebook login can "
    "optionally be protected in the OS keystore by running "
    "'nlm auth storage set protected'. Don't repeat this."
)


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch, fake_credential_store):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path))
    reset_config()
    yield
    reset_config()


def test_100_mcp_tool_calls_zero_tool_call_probes_and_no_delay(
    monkeypatch, fake_credential_store, pretend_desktop
):
    """100 MCP tool calls must never probe keystore inside tool calls and have 0 delay."""
    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "test_sid"}, email="user@example.com")

    # Start background probe and wait for it to complete
    start_mcp_background_probe(force=True)
    assert _mcp_probe_event.wait(timeout=5.0), "Background probe timed out"

    # Mock external network calls inside server_info so benchmark isolates local MCP overhead
    monkeypatch.setattr(
        "notebooklm_tools.mcp.tools.server._check_auth_status", lambda: "configured"
    )
    monkeypatch.setattr("notebooklm_tools.mcp.tools.server._get_latest_pypi_version", lambda: None)

    probe_calls = 0
    orig_probe = CredentialWorkerClient.probe

    def _spy_probe(self, service, account):
        nonlocal probe_calls
        probe_calls += 1
        return orig_probe(self, service, account)

    monkeypatch.setattr(CredentialWorkerClient, "probe", _spy_probe)

    t0 = time.perf_counter()
    for i in range(100):
        res = server_info()
        assert res["status"] == "success"
        if i == 0:
            assert res.get("user_notice") == EXPECTED_NOTICE
        else:
            assert "user_notice" not in res
        assert "storage_notice" not in res
    elapsed = time.perf_counter() - t0

    # ZERO probes occurred during the 100 tool calls
    assert probe_calls == 0
    # 100 calls should be exceedingly fast (well under 0.5 seconds total)
    assert elapsed < 1.0


def test_user_notice_sent_once_across_restarts(monkeypatch, fake_credential_store, pretend_desktop):
    """The AI receives the notice exactly once per install, even after a server restart."""
    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "test_sid"}, email="user@example.com")

    start_mcp_background_probe(force=True)
    assert _mcp_probe_event.wait(timeout=5.0), "Background probe timed out"
    assert server_info().get("user_notice") == EXPECTED_NOTICE
    assert "user_notice" not in server_info()

    # Simulated restart: a fresh background probe must not bring the notice back
    reset_mcp_probe_state()
    start_mcp_background_probe(force=True)
    assert _mcp_probe_event.wait(timeout=5.0), "Background probe timed out"
    assert "user_notice" not in server_info()


def test_user_notice_never_sent_when_already_protected(monkeypatch, fake_credential_store):
    """A profile already in protected mode never gets the notice."""
    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "test_sid"}, email="user@example.com")
    set_storage_mode("protected", "default")

    start_mcp_background_probe(force=True)
    assert _mcp_probe_event.wait(timeout=5.0), "Background probe timed out"
    assert "user_notice" not in server_info()


def test_server_info_never_probes_before_background_probe(monkeypatch, fake_credential_store):
    """Before the background probe finishes, server_info omits the notice and never probes."""
    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "test_sid"}, email="user@example.com")

    probe_calls = 0

    def counting_probe(self, *args, **kwargs):
        nonlocal probe_calls
        probe_calls += 1
        return True

    monkeypatch.setattr(CredentialWorkerClient, "probe", counting_probe)

    info = server_info()
    assert "user_notice" not in info
    assert probe_calls == 0


def test_server_info_omitted_when_keystore_unavailable(monkeypatch, fake_credential_store):
    """No notice over SSH / non-desktop sessions."""
    auth = AuthManager("default")
    auth.save_profile(cookies={"SID": "test_sid"}, email="user@example.com")

    # Simulate SSH / non-desktop session
    monkeypatch.setenv("SSH_CONNECTION", "192.168.1.1 1234 192.168.1.2 22")
    start_mcp_background_probe(force=True)
    assert _mcp_probe_event.wait(timeout=5.0), "Background probe timed out"
    assert "user_notice" not in server_info()


def test_importing_server_never_starts_probe(tmp_path):
    """Importing the server (as pytest collection does) must not start the keystore probe."""
    import os
    import subprocess
    import sys

    storage = tmp_path / "storage"
    (storage / "profiles" / "default").mkdir(parents=True)
    (storage / "profiles" / "default" / "cookies.json").write_text('{"cookies": {"SID": "x"}}')
    (storage / "profiles" / "default" / "metadata.json").write_text("{}")
    script = (
        "import notebooklm_tools.core.credential_store as cs\n"
        "cs.set_backend_factory(lambda: cs.InMemoryCredentialBackend())\n"
        "import notebooklm_tools.mcp.server\n"
        "from notebooklm_tools.mcp.tools import _utils\n"
        "print(_utils._mcp_probe_thread is None)\n"
    )
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
    env["NOTEBOOKLM_MCP_CLI_PATH"] = str(storage)
    result = subprocess.run(
        [sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"
    assert not (storage / "notices.json").exists()
