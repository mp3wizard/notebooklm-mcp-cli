"""The direct status command reports the same user-level targets as the wizard."""

import json
from pathlib import Path

from rich.console import Console

from notebooklm_tools.cli.commands import setup


def test_setup_list_shows_desktop_only_codex_config(tmp_path, monkeypatch, capsys):
    console = Console(record=True, width=180)
    monkeypatch.setattr(setup, "console", console)
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        '[mcp_servers.gemini-notebook-mcp]\ncommand = "/bin/notebooklm-mcp"\n'
    )
    monkeypatch.setattr(setup, "_codex_config_path", lambda: config_dir)
    monkeypatch.setattr(setup.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        setup,
        "CLIENT_REGISTRY",
        {"codex": {"name": "Codex", "description": "Codex", "has_auto_setup": True}},
    )

    setup.setup_list()

    output = console.export_text()
    assert "✓" in output
    assert "config.toml" in output


def test_setup_list_does_not_claim_unrelated_claude_legacy_entry(tmp_path, monkeypatch, capsys):
    console = Console(record=True, width=180)
    monkeypatch.setattr(setup, "console", console)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".claude.json").write_text(
        json.dumps({"mcpServers": {"notebooklm": {"command": "unrelated-tool"}}})
    )
    monkeypatch.setattr(
        setup.shutil, "which", lambda name: "/bin/claude" if name == "claude" else None
    )
    monkeypatch.setattr(
        setup.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"stdout": "notebooklm: unrelated-tool"})(),
    )
    monkeypatch.setattr(
        setup,
        "CLIENT_REGISTRY",
        {
            "claude-code": {
                "name": "Claude Code",
                "description": "Claude Code",
                "has_auto_setup": True,
            }
        },
    )

    setup.setup_list()

    assert "✓" not in console.export_text()


def test_setup_list_shows_global_copilot_config(tmp_path, monkeypatch, capsys):
    console = Console(record=True, width=180)
    monkeypatch.setattr(setup, "console", console)
    user_config = tmp_path / "User" / "mcp.json"
    user_config.parent.mkdir()
    user_config.write_text(
        json.dumps({"servers": {"gemini-notebook-mcp": {"command": "/bin/notebooklm-mcp"}}})
    )
    monkeypatch.setattr(
        setup,
        "_github_copilot_config_path",
        lambda scope="project": (
            user_config if scope == "user" else tmp_path / ".vscode" / "mcp.json"
        ),
    )
    monkeypatch.setattr(
        setup,
        "CLIENT_REGISTRY",
        {
            "github-copilot": {
                "name": "GitHub Copilot",
                "description": "Copilot",
                "has_auto_setup": True,
            }
        },
    )

    setup.setup_list()

    output = console.export_text()
    assert "user profile" in output
    assert "✓" in output
