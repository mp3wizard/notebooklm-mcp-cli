"""Tests for shared Codex CLI and ChatGPT Desktop configuration."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import tomlkit

from notebooklm_tools.cli.commands import setup
from notebooklm_tools.cli.setup_safety import ConfigParseError


def test_chatgpt_desktop_alias_resolves_to_codex():
    assert setup.CLIENT_ALIASES.get("chatgpt-desktop") == "codex"


def test_codex_config_path_honors_codex_home(tmp_path, monkeypatch):
    custom_home = tmp_path / "custom_codex"
    monkeypatch.setenv("CODEX_HOME", str(custom_home))
    assert setup._codex_config_path() == custom_home


def test_codex_config_path_default(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert setup._codex_config_path() == tmp_path / ".codex"


def test_detect_chatgpt_desktop_macos(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.platform, "system", lambda: "Darwin")
    fake_app = tmp_path / "Applications" / "ChatGPT.app"
    fake_app.mkdir(parents=True)
    monkeypatch.setattr(setup, "_chatgpt_desktop_candidate_paths", lambda: [fake_app])
    assert setup._detect_chatgpt_desktop() is True


def test_detect_chatgpt_desktop_not_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        setup, "_chatgpt_desktop_candidate_paths", lambda: [tmp_path / "Nonexistent.app"]
    )
    monkeypatch.setattr(
        setup.shutil, "which", lambda cmd: None if cmd == "chatgpt" else "/bin/something"
    )
    assert setup._detect_chatgpt_desktop() is False


def test_codex_cli_add_uses_absolute_server_path(tmp_path, monkeypatch):
    calls = []
    binary_path = "/opt/tools/bin/notebooklm-mcp"
    monkeypatch.setattr(
        setup.shutil,
        "which",
        lambda name: {
            "codex": "/usr/local/bin/codex",
            "notebooklm-mcp": binary_path,
        }.get(name),
    )
    monkeypatch.setattr(
        setup.subprocess,
        "run",
        lambda args, **kw: (
            calls.append(args) or SimpleNamespace(returncode=0, stdout="", stderr="")
        ),
    )
    codex_dir = tmp_path / ".codex"
    monkeypatch.setattr(setup, "_codex_config_path", lambda: codex_dir)

    assert setup._setup_codex() is True
    assert len(calls) > 0
    # First argument list should be codex mcp add with absolute server binary
    assert calls[0] == [
        "/usr/local/bin/codex",
        "mcp",
        "add",
        setup.MCP_SERVER_NAME,
        "--",
        binary_path,
    ]

    # Verify TOML updated with tool_timeout_sec = 300
    config_file = codex_dir / "config.toml"
    assert config_file.exists()
    doc = tomlkit.parse(config_file.read_text(encoding="utf-8"))
    entry = doc["mcp_servers"][setup.MCP_SERVER_NAME]
    assert entry["tool_timeout_sec"] == 300
    assert entry["command"] == binary_path


def test_codex_desktop_only_add_edits_toml_directly(tmp_path, monkeypatch):
    binary_path = "/home/user/.local/bin/notebooklm-mcp"
    monkeypatch.setattr(
        setup.shutil,
        "which",
        lambda name: binary_path if name == "notebooklm-mcp" else None,
    )
    monkeypatch.setattr(setup, "_detect_chatgpt_desktop", lambda: True)
    codex_dir = tmp_path / ".codex"
    monkeypatch.setattr(setup, "_codex_config_path", lambda: codex_dir)

    assert setup._setup_codex() is True
    config_file = codex_dir / "config.toml"
    assert config_file.exists()
    doc = tomlkit.parse(config_file.read_text(encoding="utf-8"))
    entry = doc["mcp_servers"][setup.MCP_SERVER_NAME]
    assert entry["command"] == binary_path
    assert entry["tool_timeout_sec"] == 300
    assert entry["args"] == []


def test_codex_desktop_only_remove_removes_from_toml(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda name: None)
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir(parents=True)
    config_file = codex_dir / "config.toml"
    config_file.write_text(
        """
[mcp_servers.other]
command = "other-tool"

[mcp_servers.gemini-notebook-mcp]
command = "/path/to/notebooklm-mcp"
tool_timeout_sec = 300
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(setup, "_codex_config_path", lambda: codex_dir)

    assert setup._remove_single("codex") is True
    doc = tomlkit.parse(config_file.read_text(encoding="utf-8"))
    assert setup.MCP_SERVER_NAME not in doc.get("mcp_servers", {})
    assert "other" in doc["mcp_servers"]


def test_codex_preserves_comments_and_formatting(tmp_path, monkeypatch):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir(parents=True)
    config_file = codex_dir / "config.toml"
    original_toml = """# My custom user configuration
model = "gpt-4o"

# NotebookLM MCP entry
[mcp_servers.other]
# Keep this server
command = "foo"
"""
    config_file.write_text(original_toml, encoding="utf-8")
    monkeypatch.setattr(setup, "_codex_config_path", lambda: codex_dir)

    setup._edit_codex_entry(config_file, command="/bin/notebooklm-mcp")
    updated = config_file.read_text(encoding="utf-8")
    assert "# My custom user configuration" in updated
    assert "# Keep this server" in updated
    assert 'model = "gpt-4o"' in updated


def test_codex_repair_reason_detects_issues(tmp_path, monkeypatch):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir(parents=True)
    config_file = codex_dir / "config.toml"
    binary_path = "/usr/local/bin/notebooklm-mcp"
    monkeypatch.setattr(setup, "_find_mcp_server_path", lambda: binary_path)

    # 1. Bare command
    config_file.write_text(
        '[mcp_servers.gemini-notebook-mcp]\ncommand = "notebooklm-mcp"\ntool_timeout_sec = 300\n',
        encoding="utf-8",
    )
    reason = setup._codex_repair_reason(config_file)
    assert reason is not None
    assert "not an absolute path" in reason

    # 2. Timeout too low
    config_file.write_text(
        f'[mcp_servers.gemini-notebook-mcp]\ncommand = "{binary_path}"\ntool_timeout_sec = 60\n',
        encoding="utf-8",
    )
    reason = setup._codex_repair_reason(config_file)
    assert reason is not None
    assert "timeout" in reason

    # 3. Correct entry
    config_file.write_text(
        f'[mcp_servers.gemini-notebook-mcp]\ncommand = "{binary_path}"\ntool_timeout_sec = 300\n',
        encoding="utf-8",
    )
    assert setup._codex_repair_reason(config_file) is None


def test_codex_repair_flag_updates_existing_entry(tmp_path, monkeypatch):
    binary_path = "/usr/local/bin/notebooklm-mcp"
    monkeypatch.setattr(
        setup.shutil,
        "which",
        lambda name: binary_path if name == "notebooklm-mcp" else None,
    )
    monkeypatch.setattr(setup, "_find_mcp_server_path", lambda: binary_path)
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir(parents=True)
    config_file = codex_dir / "config.toml"
    config_file.write_text(
        f'[mcp_servers.gemini-notebook-mcp]\ncommand = "{binary_path}"\ntool_timeout_sec = 60\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(setup, "_codex_config_path", lambda: codex_dir)

    # Without repair flag: skips since already configured
    setup._setup_codex(repair=False)
    doc = tomlkit.parse(config_file.read_text(encoding="utf-8"))
    assert doc["mcp_servers"][setup.MCP_SERVER_NAME]["tool_timeout_sec"] == 60

    # With repair flag: updates timeout to 300
    setup._setup_codex(repair=True)
    doc = tomlkit.parse(config_file.read_text(encoding="utf-8"))
    assert doc["mcp_servers"][setup.MCP_SERVER_NAME]["tool_timeout_sec"] == 300


def test_codex_malformed_toml_fails_closed(tmp_path, monkeypatch):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir(parents=True)
    config_file = codex_dir / "config.toml"
    bad_toml = "[mcp_servers = invalid"
    config_file.write_text(bad_toml, encoding="utf-8")
    monkeypatch.setattr(setup, "_codex_config_path", lambda: codex_dir)

    with pytest.raises(ConfigParseError):
        setup._edit_codex_entry(config_file, command="/bin/test")
    assert config_file.read_text(encoding="utf-8") == bad_toml


def test_codex_removal_preserves_unrelated_legacy_named_server(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[mcp_servers.notebooklm]\ncommand = "unrelated-tool"\n\n'
        '[mcp_servers.gemini-notebook-mcp]\ncommand = "/bin/notebooklm-mcp"\n'
    )

    setup._edit_codex_entry(config_file, remove=True)

    servers = tomlkit.parse(config_file.read_text())["mcp_servers"]
    assert "gemini-notebook-mcp" not in servers
    assert servers["notebooklm"]["command"] == "unrelated-tool"


def test_codex_add_preserves_unrelated_legacy_named_server(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    config_file = tmp_path / "config.toml"
    config_file.write_text('[mcp_servers.notebooklm]\ncommand = "unrelated-tool"\n')

    setup._edit_codex_entry(config_file, command="/bin/notebooklm-mcp")

    servers = tomlkit.parse(config_file.read_text())["mcp_servers"]
    assert servers["notebooklm"]["command"] == "unrelated-tool"
    assert servers["gemini-notebook-mcp"]["command"] == "/bin/notebooklm-mcp"


def test_codex_status_ignores_unrelated_legacy_named_server(tmp_path, monkeypatch):
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        '[mcp_servers.notebooklm]\ncommand = "unrelated-tool"\n'
    )
    monkeypatch.setattr(setup, "_codex_config_path", lambda: config_dir)
    monkeypatch.setattr(
        setup.shutil, "which", lambda name: "/bin/codex" if name == "codex" else None
    )
    monkeypatch.setattr(
        setup.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="notebooklm: unrelated-tool", stderr=""
        ),
    )

    assert setup._is_already_configured("codex") is False


def test_codex_remove_does_not_delegate_legacy_names_to_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    config_file.write_text(
        '[mcp_servers.notebooklm]\ncommand = "unrelated-tool"\n\n'
        '[mcp_servers.gemini-notebook-mcp]\ncommand = "/bin/notebooklm-mcp"\n'
    )
    monkeypatch.setattr(setup, "_codex_config_path", lambda: config_dir)
    monkeypatch.setattr(
        setup.shutil, "which", lambda name: "/bin/codex" if name == "codex" else None
    )
    monkeypatch.setattr(
        setup.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail(
            "Codex removal should edit only the recognized user config entry"
        ),
    )

    assert setup._remove_single("codex") is True
    servers = tomlkit.parse(config_file.read_text())["mcp_servers"]
    assert "gemini-notebook-mcp" not in servers
    assert servers["notebooklm"]["command"] == "unrelated-tool"
