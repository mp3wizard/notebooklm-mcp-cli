"""Tests for the wizard status view row assembly."""

from pathlib import Path

from notebooklm_tools.cli.commands import setup_wizard as w


def test_build_status_rows_all_states():
    targets = [
        w.SetupTarget("claude-code", "Claude Code", True, True, Path("/a"), "claude-code"),
        w.SetupTarget("windsurf", "Windsurf", True, False, Path("/b"), "windsurf"),
        w.SetupTarget("claude-desktop", "Claude Desktop", True, False, Path("/c"), None),
    ]

    def state_fn(target):
        return {
            "claude-code": {
                "supported": True,
                "installed": True,
                "version": "0.1.0",
                "package_version": "0.2.0",
                "upgrade_available": True,
            },
            "windsurf": {
                "supported": True,
                "installed": False,
                "version": None,
                "package_version": "0.2.0",
                "upgrade_available": False,
            },
            "claude-desktop": {
                "supported": False,
                "installed": False,
                "version": None,
                "package_version": "0.2.0",
                "upgrade_available": False,
            },
        }[target.id]

    rows = {r["tool"]: r for r in w.build_status_rows(targets, state_fn)}
    assert rows["Claude Code"]["connection"] == "✓ set up"
    assert "⬆" in rows["Claude Code"]["skill"] and "0.2.0" in rows["Claude Code"]["skill"]
    assert rows["Windsurf"]["connection"] == "✗ not yet"
    assert rows["Windsurf"]["skill"] == "✗ not yet"
    assert rows["Claude Desktop"]["skill"] == "– n/a"


def test_status_markup_colors_by_glyph():
    from notebooklm_tools.cli.commands import setup_wizard as w

    assert w._status_markup("✓ set up") == "[green]✓ set up[/green]"
    assert w._status_markup("✗ not yet") == "[red]✗ not yet[/red]"
    assert w._status_markup("⬆ v0.12.0 → v0.13.0") == "[yellow]⬆ v0.12.0 → v0.13.0[/yellow]"
    assert w._status_markup("– n/a") == "[dim]– n/a[/dim]"
    assert w._status_markup("plain") == "plain"


def test_build_status_rows_current_skill_shows_version():
    targets = [w.SetupTarget("cursor", "Cursor", True, True, Path("/a"), "cursor")]

    def state_fn(target):
        return {
            "supported": True,
            "installed": True,
            "version": "0.2.0",
            "package_version": "0.2.0",
            "upgrade_available": False,
        }

    row = w.build_status_rows(targets, state_fn)[0]
    assert row["skill"] == "✓ v0.2.0"
