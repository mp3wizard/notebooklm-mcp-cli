"""Tests for the Copy-JSON snippet builder."""

from notebooklm_tools.cli.commands import setup


def test_snippet_default_uses_full_path(monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda _: "/opt/bin/notebooklm-mcp")
    snip = setup.build_json_snippet()
    entry = snip["mcpServers"][setup.MCP_SERVER_NAME]
    assert entry["command"] == "/opt/bin/notebooklm-mcp"


def test_snippet_full_path_fallback_bare(monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda _: None)
    entry = setup.build_json_snippet()["mcpServers"][setup.MCP_SERVER_NAME]
    assert entry["command"] == "notebooklm-mcp"


def test_snippet_bare_command_when_not_full_path(monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda _: "/opt/bin/notebooklm-mcp")
    entry = setup.build_json_snippet(use_full_path=False)["mcpServers"][setup.MCP_SERVER_NAME]
    assert entry["command"] == "notebooklm-mcp"


def test_snippet_uvx_and_unwrapped():
    snip = setup.build_json_snippet(config_type="uvx", wrap=False)
    assert snip[setup.MCP_SERVER_NAME]["command"] == "uvx"
    assert snip[setup.MCP_SERVER_NAME]["args"] == ["--from", "notebooklm-mcp-cli", "notebooklm-mcp"]
    assert "mcpServers" not in snip


def test_json_screen_notes_when_path_undetected(monkeypatch, capsys):
    from types import SimpleNamespace

    from notebooklm_tools.cli.commands import setup_wizard

    monkeypatch.setattr(setup.shutil, "which", lambda _: None)
    monkeypatch.setattr(setup_wizard, "copy_to_clipboard", lambda v: True)
    monkeypatch.setattr(
        setup.questionary, "select", lambda *a, **k: SimpleNamespace(ask=lambda: "No, I'm done")
    )
    setup._setup_json()
    out = capsys.readouterr().out.lower()
    assert "on your path" in out


def test_json_screen_no_note_when_path_detected(monkeypatch, capsys):
    from types import SimpleNamespace

    from notebooklm_tools.cli.commands import setup_wizard

    monkeypatch.setattr(setup.shutil, "which", lambda _: "/opt/bin/notebooklm-mcp")
    monkeypatch.setattr(setup_wizard, "copy_to_clipboard", lambda v: True)
    monkeypatch.setattr(
        setup.questionary, "select", lambda *a, **k: SimpleNamespace(ask=lambda: "No, I'm done")
    )
    setup._setup_json()
    out = capsys.readouterr().out.lower()
    assert "on your path" not in out
