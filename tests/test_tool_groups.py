"""Tests for optional MCP tool-group gating."""

from unittest.mock import MagicMock

from notebooklm_tools.mcp import tool_groups

_ENV_VARS = (
    "NOTEBOOKLM_DISABLED_GROUPS",
    "NOTEBOOKLM_DISABLED_TOOLS",
    "NOTEBOOKLM_ENABLED_TOOLS",
)


def _clear_env(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_no_config_hides_nothing(monkeypatch):
    _clear_env(monkeypatch)
    assert tool_groups._resolve_disabled() == set()


def test_disabled_group_hides_its_tools(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("NOTEBOOKLM_DISABLED_GROUPS", "studio")
    assert tool_groups._resolve_disabled() == tool_groups.TOOL_GROUPS["studio"]


def test_multiple_groups_are_unioned(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("NOTEBOOKLM_DISABLED_GROUPS", "notes, sharing")
    expected = tool_groups.TOOL_GROUPS["notes"] | tool_groups.TOOL_GROUPS["sharing"]
    assert tool_groups._resolve_disabled() == expected


def test_unknown_group_is_ignored(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("NOTEBOOKLM_DISABLED_GROUPS", "does_not_exist")
    assert tool_groups._resolve_disabled() == set()


def test_disabled_tools_add_single_names(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("NOTEBOOKLM_DISABLED_TOOLS", "notebook_query, note")
    assert tool_groups._resolve_disabled() == {"notebook_query", "note"}


def test_enabled_tools_override_disabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("NOTEBOOKLM_DISABLED_GROUPS", "studio")
    monkeypatch.setenv("NOTEBOOKLM_ENABLED_TOOLS", "studio_status")
    result = tool_groups._resolve_disabled()
    assert "studio_status" not in result
    assert "studio_create" in result


def test_apply_disables_resolved_names(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("NOTEBOOKLM_DISABLED_GROUPS", "notes")
    mcp = MagicMock()

    hidden = tool_groups.apply(mcp)

    assert hidden == tool_groups.TOOL_GROUPS["notes"]
    mcp.local_provider.disable.assert_called_once_with(names=hidden)


def test_apply_noop_when_nothing_disabled(monkeypatch):
    _clear_env(monkeypatch)
    mcp = MagicMock()

    hidden = tool_groups.apply(mcp)

    assert hidden == set()
    mcp.local_provider.disable.assert_not_called()


def test_groups_are_disjoint():
    seen: dict[str, str] = {}
    for group, names in tool_groups.TOOL_GROUPS.items():
        for name in names:
            assert name not in seen, f"{name} in both {seen.get(name)} and {group}"
            seen[name] = group


def test_groups_cover_every_registered_tool():
    """TOOL_GROUPS must cover every tool the server actually registers.

    A tool missing from every group can never be hidden via
    NOTEBOOKLM_DISABLED_GROUPS, silently breaking the "opt-in gating" promise
    for that tool. This caught chat_list/chat_get/chat_export shipping without
    a group assignment.
    """
    import notebooklm_tools.mcp.server  # noqa: F401 — populates the tool registry on import
    from notebooklm_tools.mcp.tools._utils import _tool_registry

    registered = {name for name, _ in _tool_registry}
    grouped = set().union(*tool_groups.TOOL_GROUPS.values())

    assert registered - grouped == set(), f"Registered but ungrouped: {registered - grouped}"
    assert grouped - registered == set(), f"Grouped but not registered: {grouped - registered}"
