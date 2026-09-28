"""Tests for skill.skill_version_state (install + version + upgrade info)."""

from pathlib import Path

from notebooklm_tools import __version__
from notebooklm_tools.cli.commands import skill


def test_version_state_unsupported_tool(monkeypatch):
    monkeypatch.setattr(skill, "get_skill_destination", lambda t, level: None)
    state = skill.skill_version_state("claude-desktop", "user")
    assert state["supported"] is False
    assert state["installed"] is False


def test_version_state_current(monkeypatch):
    monkeypatch.setattr(skill, "get_skill_destination", lambda t, level: Path("/x"))
    monkeypatch.setattr(skill, "check_install_status", lambda t, level: (True, None))
    monkeypatch.setattr(skill, "_get_installed_version", lambda t, level: __version__)
    state = skill.skill_version_state("cursor", "user")
    assert state["installed"] is True
    assert state["upgrade_available"] is False
    assert state["version"] == __version__


def test_version_state_upgrade(monkeypatch):
    monkeypatch.setattr(skill, "get_skill_destination", lambda t, level: Path("/x"))
    monkeypatch.setattr(skill, "check_install_status", lambda t, level: (True, None))
    monkeypatch.setattr(skill, "_get_installed_version", lambda t, level: "0.0.1")
    state = skill.skill_version_state("cursor", "user")
    assert state["upgrade_available"] is True
    assert state["version"] == "0.0.1"


def test_version_state_unversioned_is_upgradeable(monkeypatch):
    monkeypatch.setattr(skill, "get_skill_destination", lambda t, level: Path("/x"))
    monkeypatch.setattr(skill, "check_install_status", lambda t, level: (True, None))
    monkeypatch.setattr(skill, "_get_installed_version", lambda t, level: None)
    state = skill.skill_version_state("cursor", "user")
    assert state["installed"] is True
    assert state["version"] is None
    assert state["upgrade_available"] is True


def test_version_state_not_installed(monkeypatch):
    monkeypatch.setattr(skill, "get_skill_destination", lambda t, level: Path("/x"))
    monkeypatch.setattr(skill, "check_install_status", lambda t, level: (False, None))
    state = skill.skill_version_state("cursor", "user")
    assert state["supported"] is True
    assert state["installed"] is False
    assert state["upgrade_available"] is False
