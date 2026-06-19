"""Tests for the `nlm source list` CLI command."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from notebooklm_tools.cli.commands.source import app


def test_source_list_drive_skip_freshness_does_not_check_sources():
    client = MagicMock()
    client.__enter__ = lambda s: s
    client.__exit__ = MagicMock(return_value=False)
    client.get_notebook_sources_with_types.return_value = [
        {
            "id": "s1",
            "title": "Drive Source",
            "source_type_name": "Drive",
            "can_sync": True,
        }
    ]

    alias_mgr = MagicMock()
    alias_mgr.resolve.side_effect = lambda value: value

    with (
        patch("notebooklm_tools.cli.commands.source.get_alias_manager", return_value=alias_mgr),
        patch("notebooklm_tools.cli.commands.source.get_client", return_value=client),
    ):
        result = CliRunner().invoke(app, ["list", "nb-1", "--drive", "--skip-freshness"])

    assert result.exit_code == 0
    client.check_source_freshness.assert_not_called()


def test_source_list_drive_skip_freshness_reports_unknown_stale_status():
    client = MagicMock()
    client.__enter__ = lambda s: s
    client.__exit__ = MagicMock(return_value=False)
    client.get_notebook_sources_with_types.return_value = [
        {
            "id": "s1",
            "title": "Drive Source",
            "source_type_name": "Drive",
            "can_sync": True,
        }
    ]

    alias_mgr = MagicMock()
    alias_mgr.resolve.side_effect = lambda value: value

    with (
        patch("notebooklm_tools.cli.commands.source.get_alias_manager", return_value=alias_mgr),
        patch("notebooklm_tools.cli.commands.source.get_client", return_value=client),
    ):
        result = CliRunner().invoke(
            app,
            ["list", "nb-1", "--drive", "--skip-freshness", "--json"],
        )

    assert result.exit_code == 0
    assert json.loads(result.output)[0]["is_stale"] is None
