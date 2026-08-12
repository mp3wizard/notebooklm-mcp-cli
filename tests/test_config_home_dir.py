from __future__ import annotations

import importlib
from pathlib import Path

from notebooklm_tools.utils import config


def _raise_missing_home() -> Path:
    raise RuntimeError("Could not determine home directory.")


def test_get_home_dir_falls_back_to_userprofile(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", _raise_missing_home)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("NOTEBOOKLM_MCP_CLI_PATH", raising=False)

    assert config.get_home_dir() == tmp_path


def test_get_home_dir_prefers_explicit_storage_parent(monkeypatch, tmp_path: Path) -> None:
    storage = tmp_path / "state" / ".notebooklm-mcp-cli"
    monkeypatch.setattr(Path, "home", _raise_missing_home)
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "stale-home"))
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(storage))

    assert config.get_home_dir() == storage.parent


def test_get_home_dir_has_deterministic_cwd_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", _raise_missing_home)
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("NOTEBOOKLM_MCP_CLI_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    assert config.get_home_dir() == tmp_path / ".notebooklm-home"


def test_config_module_reload_survives_missing_os_home(monkeypatch, tmp_path: Path) -> None:
    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "home", _raise_missing_home)
        scoped.setenv("USERPROFILE", str(tmp_path))
        scoped.delenv("HOME", raising=False)
        scoped.delenv("NOTEBOOKLM_MCP_CLI_PATH", raising=False)

        reloaded = importlib.reload(config)

        assert reloaded.OLD_CHROME_PROFILES[0].is_relative_to(tmp_path)
        assert reloaded.OLD_AUTH_LOCATIONS[0].is_relative_to(tmp_path)

    importlib.reload(config)


def test_windows_browser_discovery_survives_missing_os_home(monkeypatch, tmp_path: Path) -> None:
    from notebooklm_tools.utils import cdp

    storage = tmp_path / "state" / ".notebooklm-mcp-cli"
    monkeypatch.setattr(Path, "home", _raise_missing_home)
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(storage))

    candidates = cdp._windows_browser_candidates()

    assert any(str(storage.parent / "AppData" / "Local") in path for _, path in candidates)
