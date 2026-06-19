"""Tests for MCP source tools."""

from unittest.mock import MagicMock, patch

from notebooklm_tools.mcp.tools.sources import source_list_drive


def test_source_list_drive_forwards_skip_freshness():
    client = MagicMock()
    service_result = {
        "drive_sources": [],
        "other_sources": [],
        "drive_count": 0,
        "stale_count": 0,
    }

    with (
        patch("notebooklm_tools.mcp.tools.sources.get_client", return_value=client),
        patch(
            "notebooklm_tools.mcp.tools.sources.sources_service.list_drive_sources",
            return_value=service_result,
        ) as list_drive_sources,
    ):
        result = source_list_drive("nb-1", skip_freshness=True)

    assert result["status"] == "success"
    list_drive_sources.assert_called_once_with(client, "nb-1", skip_freshness=True)
