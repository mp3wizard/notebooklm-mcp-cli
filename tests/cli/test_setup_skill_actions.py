"""Tests for safe skill actions: backup, deduplication, and version checking."""

from pathlib import Path

from notebooklm_tools import __version__
from notebooklm_tools.cli.commands import skill


def test_newer_skill_is_never_downgraded(monkeypatch, tmp_path):
    skill_dir = tmp_path / "nlm-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text('---\nversion: "99.0.0"\n---\n', encoding="utf-8")
    monkeypatch.setitem(skill.TOOL_CONFIGS, "agents", {"user": skill_dir, "format": "skill.md"})

    result = skill.skill_action("agents", "user", "install", confirm_replace=lambda _: True)
    assert result.status == "newer"
    assert "99.0.0" in (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def test_current_skill_is_skipped(monkeypatch, tmp_path):
    skill_dir = tmp_path / "nlm-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(f'---\nversion: "{__version__}"\n---\n', encoding="utf-8")
    monkeypatch.setitem(skill.TOOL_CONFIGS, "agents", {"user": skill_dir, "format": "skill.md"})

    result = skill.skill_action("agents", "user", "install", confirm_replace=lambda _: True)
    assert result.status == "current"


def test_older_skill_upgrade_requires_confirmation_and_creates_backup(monkeypatch, tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    skill_dir = tmp_path / "nlm-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text('---\nversion: "0.0.1"\n---\n', encoding="utf-8")
    monkeypatch.setitem(skill.TOOL_CONFIGS, "agents", {"user": skill_dir, "format": "skill.md"})

    prompted = []

    def mock_confirm(msg):
        prompted.append(msg)
        return True

    result = skill.skill_action("agents", "user", "install", confirm_replace=mock_confirm)
    assert result.status == "updated"
    assert len(prompted) == 1
    assert "0.0.1" in prompted[0]
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert (result.backup_path / "SKILL.md").read_text(
        encoding="utf-8"
    ) == '---\nversion: "0.0.1"\n---\n'
    assert f'version: "{__version__}"' in (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def test_older_skill_replacement_declined(monkeypatch, tmp_path):
    skill_dir = tmp_path / "nlm-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text('---\nversion: "0.0.1"\n---\n', encoding="utf-8")
    monkeypatch.setitem(skill.TOOL_CONFIGS, "agents", {"user": skill_dir, "format": "skill.md"})

    result = skill.skill_action("agents", "user", "install", confirm_replace=lambda _: False)
    assert result.status == "skipped"
    assert "0.0.1" in (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def test_skill_removal_creates_backup_and_deletes_folder(monkeypatch, tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    skill_dir = tmp_path / "nlm-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: custom\n---\n", encoding="utf-8")
    monkeypatch.setitem(skill.TOOL_CONFIGS, "agents", {"user": skill_dir, "format": "skill.md"})

    result = skill.skill_action("agents", "user", "remove", confirm_replace=lambda _: True)
    assert result.status == "removed"
    assert not skill_dir.exists()
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert (result.backup_path / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "---\nname: custom\n---\n"


def test_skill_backup_failure_aborts_mutation(monkeypatch, tmp_path):
    skill_dir = tmp_path / "nlm-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: important\n---\n", encoding="utf-8")
    monkeypatch.setitem(skill.TOOL_CONFIGS, "agents", {"user": skill_dir, "format": "skill.md"})
    monkeypatch.setattr(
        skill,
        "backup_existing",
        lambda *a, **kw: (_ for _ in ()).throw(PermissionError("backup denied")),
    )

    result = skill.skill_action("agents", "user", "remove", confirm_replace=lambda _: True)
    assert result.status == "failed"
    assert (skill_dir / "SKILL.md").exists()


def test_chatgpt_desktop_shares_agents_path(monkeypatch, tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    res_codex = skill.get_skill_destination("codex", "user")
    res_chatgpt = skill.get_skill_destination("chatgpt-desktop", "user")
    assert res_codex == res_chatgpt
    assert res_codex == skill._AGENTS_USER


def test_claude_desktop_has_no_local_skill():
    dest = skill.get_skill_destination("claude-desktop", "user")
    assert dest is None
    result = skill.skill_action("claude-desktop", "user", "install")
    assert result.status == "failed"
    assert "not supported" in result.message.lower() or "mcp-only" in result.message.lower()
