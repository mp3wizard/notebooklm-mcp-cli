"""Tests for bundled cross-MCP workflow contracts."""

from pathlib import Path


def test_bundled_skill_routes_bounded_public_x_research():
    skill = Path("src/notebooklm_tools/data/SKILL.md").read_text(encoding="utf-8")
    workflows = Path("src/notebooklm_tools/data/references/workflows.md").read_text(
        encoding="utf-8"
    )

    assert "Workflow 16" in skill
    assert "https://xquik.com/mcp" in workflows
    assert 'xquik.request("/api/v1/x/tweets/search"' in workflows
    assert 'source_type="text"' in workflows
    assert "returned cursor" in workflows
    assert "untrusted data" in workflows
    assert "Private reads, writes, monitors" in workflows
    assert "copy credentials" in workflows
