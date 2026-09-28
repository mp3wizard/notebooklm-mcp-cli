"""Tests for full-detected-binary-path defaults in MCP setup entries."""

from notebooklm_tools.cli.commands import setup


def test_default_server_command_prefers_full_path(monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda _: "/opt/bin/notebooklm-mcp")
    assert setup._default_server_command() == "/opt/bin/notebooklm-mcp"


def test_default_server_command_falls_back_to_bare(monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda _: None)
    assert setup._default_server_command() == "notebooklm-mcp"


def test_add_mcp_server_writes_full_path(monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda _: "/opt/bin/notebooklm-mcp")
    cfg = setup._add_mcp_server({})
    entry = cfg["mcpServers"][setup.MCP_SERVER_NAME]
    assert entry["command"] == "/opt/bin/notebooklm-mcp"
    assert entry["args"] == []


def test_add_vscode_mcp_server_writes_full_path(monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda _: "/opt/bin/notebooklm-mcp")
    cfg = setup._add_vscode_mcp_server({})
    assert cfg["servers"][setup.MCP_SERVER_NAME]["command"] == "/opt/bin/notebooklm-mcp"
