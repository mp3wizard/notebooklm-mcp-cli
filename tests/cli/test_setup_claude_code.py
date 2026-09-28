"""Safety checks for Claude Code's user-level MCP configuration."""

import json
from pathlib import Path
from types import SimpleNamespace

from notebooklm_tools.cli.commands import setup


def test_claude_code_add_backs_up_existing_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / ".notebooklm-mcp-cli"))
    config = tmp_path / ".claude.json"
    original = '{"mcpServers": {"other": {"command": "other-tool"}}}'
    config.write_text(original)
    monkeypatch.setattr(
        setup.shutil, "which", lambda name: "/bin/claude" if name == "claude" else None
    )
    monkeypatch.setattr(
        setup.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stderr="", stdout=""),
    )

    assert setup._setup_claude_code() is True
    backups = list((tmp_path / ".notebooklm-mcp-cli" / "backups").iterdir())
    assert len(backups) == 1
    assert backups[0].read_text() == original


def test_claude_code_status_ignores_unrelated_legacy_name(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / ".notebooklm-mcp-cli"))
    (tmp_path / ".claude.json").write_text(
        json.dumps({"mcpServers": {"notebooklm": {"command": "unrelated-tool"}}})
    )
    monkeypatch.setattr(
        setup.shutil, "which", lambda name: "/bin/claude" if name == "claude" else None
    )
    monkeypatch.setattr(
        setup.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="notebooklm: unrelated-tool", stderr=""
        ),
    )

    assert setup._is_already_configured("claude-code") is False


def test_claude_code_remove_only_targets_its_own_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / ".notebooklm-mcp-cli"))
    config = tmp_path / ".claude.json"
    config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "gemini-notebook-mcp": {"command": "notebooklm-mcp"},
                    "notebooklm": {"command": "unrelated-tool"},
                }
            }
        )
    )
    monkeypatch.setattr(
        setup.shutil, "which", lambda name: "/bin/claude" if name == "claude" else None
    )
    removed = []

    def fake_run(args, **kwargs):
        removed.append(args[-1])
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(setup.subprocess, "run", fake_run)

    assert setup._remove_single("claude-code") is True
    assert removed == ["gemini-notebook-mcp"]
    assert list((tmp_path / ".notebooklm-mcp-cli" / "backups").iterdir())
