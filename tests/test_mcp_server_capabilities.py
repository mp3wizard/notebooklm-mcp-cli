"""Tests for conservative server capability reporting."""

from unittest.mock import patch

from notebooklm_tools.mcp.tools.server import _runtime_capabilities, server_info


def test_runtime_capabilities_report_complete_and_partial_groups():
    registered = {
        "notebook_list",
        "notebook_get",
        "notebook_describe",
        "notebook_query",
        "notebook_query_start",
        "notebook_query_status",
        "extension_tool",
    }
    disabled = {"notebook_get", "notebook_query_status"}

    result = _runtime_capabilities(registered, disabled)

    notebooks = result["groups"]["notebooks_read"]
    assert notebooks["available"] is False
    assert notebooks["partially_available"] is True
    assert notebooks["visible_tools"] == ["notebook_describe", "notebook_list"]
    assert notebooks["hidden_tools"] == ["notebook_get"]
    assert notebooks["missing_tools"] == []

    chat = result["groups"]["chat"]
    assert chat["available"] is False
    assert chat["partially_available"] is True
    assert "notebook_query_status" in chat["hidden_tools"]

    assert result["registered_tool_count"] == 7
    assert result["visible_tool_count"] == 5
    assert result["hidden_tool_count"] == 2
    assert result["ungrouped_tools"] == ["extension_tool"]


def test_empty_group_is_not_reported_as_available():
    result = _runtime_capabilities({"server_info"}, set())

    assert result["groups"]["server"]["available"] is True
    assert result["groups"]["research"]["available"] is False
    assert result["groups"]["research"]["partially_available"] is False
    assert result["groups"]["research"]["missing_tools"] == [
        "research_import",
        "research_start",
        "research_status",
    ]


def test_group_with_only_one_registered_tool_is_partial_not_available():
    result = _runtime_capabilities({"notebook_list"}, set())

    group = result["groups"]["notebooks_read"]
    assert group["available"] is False
    assert group["partially_available"] is True
    assert group["visible_tools"] == ["notebook_list"]
    assert group["missing_tools"] == ["notebook_describe", "notebook_get"]


def test_server_info_marks_provider_capabilities_unprobed():
    with (
        patch(
            "notebooklm_tools.mcp.tools.server._get_latest_pypi_version",
            return_value=None,
        ),
        patch(
            "notebooklm_tools.mcp.tools.server._check_auth_status",
            return_value="configured",
        ),
        patch(
            "notebooklm_tools.mcp.tools.server._runtime_capabilities",
            return_value={"schema_version": 1, "scope": "built_in_mcp_runtime"},
        ),
    ):
        result = server_info()

    assert result["status"] == "success"
    assert result["mcp_capabilities"] == {
        "schema_version": 1,
        "scope": "built_in_mcp_runtime",
    }
    assert result["provider_capabilities"]["status"] == "not_probed"
    assert "plan labels" in result["provider_capabilities"]["reason"]
