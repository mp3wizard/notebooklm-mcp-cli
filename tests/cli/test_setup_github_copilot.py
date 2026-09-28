"""Tests for GitHub Copilot support in ``nlm setup add/remove/list``."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from notebooklm_tools.cli.commands import setup
from notebooklm_tools.cli.commands.setup import (
    CLIENT_REGISTRY,
    MCP_SERVER_CMD,
    MCP_SERVER_NAME,
    _detect_tool,
    _github_copilot_config_path,
    _is_already_configured,
    _remove_single,
    _setup_github_copilot,
)


class TestGitHubCopilotRegistry:
    """Verify GitHub Copilot is properly registered in CLIENT_REGISTRY."""

    def test_github_copilot_in_registry(self):
        assert "github-copilot" in CLIENT_REGISTRY

    def test_github_copilot_has_auto_setup(self):
        assert CLIENT_REGISTRY["github-copilot"]["has_auto_setup"] is True

    def test_github_copilot_name(self):
        assert CLIENT_REGISTRY["github-copilot"]["name"] == "GitHub Copilot"


class TestGitHubCopilotConfigPath:
    """Verify workspace config path resolution."""

    def test_config_path_is_workspace_vscode_mcp_json(self):
        path = _github_copilot_config_path()
        assert path == Path(".vscode") / "mcp.json"


class TestSetupGitHubCopilot:
    """Test ``_setup_github_copilot()`` writes the correct config format."""

    def test_creates_config_from_scratch(self, tmp_path):
        config_path = tmp_path / ".vscode" / "mcp.json"
        with patch(
            "notebooklm_tools.cli.commands.setup._github_copilot_config_path",
            return_value=config_path,
        ):
            result = _setup_github_copilot()

        assert result is True
        config = json.loads(config_path.read_text())
        assert "servers" in config
        assert MCP_SERVER_NAME in config["servers"]
        assert "notebooklm-mcp" not in config["servers"]
        entry = config["servers"][MCP_SERVER_NAME]
        assert entry["command"] == setup._default_server_command()
        assert entry["args"] == []

    def test_preserves_existing_config_keys(self, tmp_path):
        config_path = tmp_path / ".vscode" / "mcp.json"
        existing = {
            "inputs": [{"type": "promptString", "id": "token"}],
            "servers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}},
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(existing))

        with patch(
            "notebooklm_tools.cli.commands.setup._github_copilot_config_path",
            return_value=config_path,
        ):
            _setup_github_copilot()

        config = json.loads(config_path.read_text())
        assert config["inputs"] == existing["inputs"]
        assert "fetch" in config["servers"]
        assert MCP_SERVER_NAME in config["servers"]

    def test_skips_if_already_configured(self, tmp_path):
        config_path = tmp_path / ".vscode" / "mcp.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps({"servers": {MCP_SERVER_NAME: {"command": MCP_SERVER_CMD, "args": []}}})
        )

        with patch(
            "notebooklm_tools.cli.commands.setup._github_copilot_config_path",
            return_value=config_path,
        ):
            result = _setup_github_copilot()

        assert result is True

    def test_uses_servers_key_not_mcpservers(self, tmp_path):
        config_path = tmp_path / ".vscode" / "mcp.json"
        with patch(
            "notebooklm_tools.cli.commands.setup._github_copilot_config_path",
            return_value=config_path,
        ):
            _setup_github_copilot()

        config = json.loads(config_path.read_text())
        assert "servers" in config
        assert "mcpServers" not in config


class TestIsAlreadyConfigured:
    """Test ``_is_already_configured()`` for GitHub Copilot."""

    def test_detects_notebooklm_key(self, tmp_path):
        config_path = tmp_path / ".vscode" / "mcp.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps({"servers": {"notebooklm": {"command": MCP_SERVER_CMD}}}))
        with patch(
            "notebooklm_tools.cli.commands.setup._github_copilot_config_path",
            return_value=config_path,
        ):
            assert _is_already_configured("github-copilot") is True

    def test_returns_false_when_not_configured(self, tmp_path):
        config_path = tmp_path / ".vscode" / "mcp.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps({"servers": {}}))
        with patch(
            "notebooklm_tools.cli.commands.setup._github_copilot_config_path",
            return_value=config_path,
        ):
            assert _is_already_configured("github-copilot") is False

    def test_returns_false_when_no_config_file(self, tmp_path):
        config_path = tmp_path / ".vscode" / "mcp.json"
        with patch(
            "notebooklm_tools.cli.commands.setup._github_copilot_config_path",
            return_value=config_path,
        ):
            assert _is_already_configured("github-copilot") is False


class TestDetectTool:
    """Test ``_detect_tool()`` for GitHub Copilot."""

    def test_detects_via_which(self):
        with patch("shutil.which", return_value="/usr/bin/code"):
            assert _detect_tool("github-copilot") is True

    def test_detects_via_workspace_directory(self, tmp_path):
        config_path = tmp_path / ".vscode" / "mcp.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with (
            patch("shutil.which", return_value=None),
            patch(
                "notebooklm_tools.cli.commands.setup._github_copilot_config_path",
                return_value=config_path,
            ),
        ):
            assert _detect_tool("github-copilot") is True

    def test_not_detected_when_absent(self, tmp_path):
        config_path = tmp_path / ".vscode" / "mcp.json"
        with (
            patch("shutil.which", return_value=None),
            patch(
                "notebooklm_tools.cli.commands.setup._github_copilot_config_path",
                return_value=config_path,
            ),
        ):
            assert _detect_tool("github-copilot") is False


class TestRemoveGitHubCopilot:
    """Test ``_remove_single()`` for GitHub Copilot."""

    def test_removes_notebooklm_entry(self, tmp_path):
        config_path = tmp_path / ".vscode" / "mcp.json"
        config = {
            "inputs": [{"type": "promptString"}],
            "servers": {
                MCP_SERVER_NAME: {"command": MCP_SERVER_CMD, "args": []},
                "fetch": {"command": "uvx", "args": ["mcp-server-fetch"]},
            },
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config))

        with patch(
            "notebooklm_tools.cli.commands.setup._github_copilot_config_path",
            return_value=config_path,
        ):
            result = _remove_single("github-copilot")

        assert result is True
        updated = json.loads(config_path.read_text())
        assert MCP_SERVER_NAME not in updated["servers"]
        assert "fetch" in updated["servers"]
        assert updated["inputs"] == config["inputs"]

    def test_returns_false_when_not_configured(self, tmp_path):
        config_path = tmp_path / ".vscode" / "mcp.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps({"servers": {}}))

        with patch(
            "notebooklm_tools.cli.commands.setup._github_copilot_config_path",
            return_value=config_path,
        ):
            result = _remove_single("github-copilot")

        assert result is False

    def test_returns_false_when_no_config_file(self, tmp_path):
        config_path = tmp_path / ".vscode" / "mcp.json"
        with patch(
            "notebooklm_tools.cli.commands.setup._github_copilot_config_path",
            return_value=config_path,
        ):
            result = _remove_single("github-copilot")

        assert result is False


class TestGitHubCopilotUserScope:
    """Tests for user-scoped GitHub Copilot / VS Code MCP setup."""

    def test_user_config_path_macos(self, tmp_path, monkeypatch):
        monkeypatch.setattr(setup.platform, "system", lambda: "Darwin")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        path = setup._github_copilot_config_path(scope="user")
        assert path == tmp_path / "Library" / "Application Support" / "Code" / "User" / "mcp.json"

    def test_user_config_path_windows(self, tmp_path, monkeypatch):
        monkeypatch.setattr(setup.platform, "system", lambda: "Windows")
        appdata = tmp_path / "AppData" / "Roaming"
        monkeypatch.setenv("APPDATA", str(appdata))
        path = setup._github_copilot_config_path(scope="user")
        assert path == appdata / "Code" / "User" / "mcp.json"

    def test_user_config_path_linux(self, tmp_path, monkeypatch):
        monkeypatch.setattr(setup.platform, "system", lambda: "Linux")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        path = setup._github_copilot_config_path(scope="user")
        assert path == tmp_path / ".config" / "Code" / "User" / "mcp.json"

    def test_setup_user_scope_via_code_cli(self, tmp_path, monkeypatch):
        calls = []
        user_config = tmp_path / "User" / "mcp.json"
        monkeypatch.setattr(
            setup,
            "_github_copilot_config_path",
            lambda scope="project": (
                user_config if scope == "user" else tmp_path / ".vscode" / "mcp.json"
            ),
        )
        monkeypatch.setattr(
            setup.shutil,
            "which",
            lambda cmd: "/usr/bin/code" if cmd == "code" else "/bin/notebooklm-mcp",
        )
        monkeypatch.setattr(setup, "_find_mcp_server_path", lambda: "/bin/notebooklm-mcp")
        monkeypatch.setattr(
            setup.subprocess,
            "run",
            lambda args, **kw: (
                calls.append(args) or SimpleNamespace(returncode=0, stdout="", stderr="")
            ),
        )
        assert setup._setup_github_copilot(scope="user") is True
        assert len(calls) == 1
        assert calls[0][0] == "/usr/bin/code"
        assert calls[0][1] == "--add-mcp"
        payload = json.loads(calls[0][2])
        assert payload["name"] == setup.MCP_SERVER_NAME
        assert payload["command"] == "/bin/notebooklm-mcp"

    def test_unknown_copilot_profile_does_not_write_project_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            setup,
            "_github_copilot_config_path",
            lambda scope="project": None if scope == "user" else tmp_path / ".vscode" / "mcp.json",
        )
        assert setup._setup_github_copilot(scope="user") is False
        assert not (tmp_path / ".vscode" / "mcp.json").exists()

    def test_remove_github_copilot_user_scope(self, tmp_path, monkeypatch):
        user_config = tmp_path / "User" / "mcp.json"
        user_config.parent.mkdir(parents=True)
        user_config.write_text(
            json.dumps(
                {
                    "servers": {
                        setup.MCP_SERVER_NAME: {"command": setup.MCP_SERVER_CMD},
                        "other": {"command": "other"},
                    }
                }
            )
        )
        monkeypatch.setattr(
            setup,
            "_github_copilot_config_path",
            lambda scope="project": (
                user_config if scope == "user" else tmp_path / ".vscode" / "mcp.json"
            ),
        )
        assert setup._remove_single("github-copilot", scope="user") is True
        data = json.loads(user_config.read_text())
        assert setup.MCP_SERVER_NAME not in data["servers"]
        assert "other" in data["servers"]

    def test_remove_github_copilot_jsonc_refusal(self, tmp_path, monkeypatch):
        user_config = tmp_path / "User" / "mcp.json"
        user_config.parent.mkdir(parents=True)
        jsonc = """{
            // Comment that would be destroyed by json.loads
            "servers": {
                "gemini-notebook-mcp": {
                    "command": "notebooklm-mcp",
                }
            }
        }"""
        user_config.write_text(jsonc, encoding="utf-8")
        monkeypatch.setattr(
            setup,
            "_github_copilot_config_path",
            lambda scope="project": (
                user_config if scope == "user" else tmp_path / ".vscode" / "mcp.json"
            ),
        )
        assert setup._remove_single("github-copilot", scope="user") is False
        assert user_config.read_text(encoding="utf-8") == jsonc
