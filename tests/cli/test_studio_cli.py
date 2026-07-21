"""Tests for Studio CLI commands."""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from notebooklm_tools.cli.commands.studio import app, slides_app, video_app
from notebooklm_tools.services.errors import ServiceError


@pytest.fixture
def runner():
    return CliRunner()


def test_slides_revise_surfaces_service_hint(runner):
    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    alias_mgr = MagicMock()
    alias_mgr.resolve.side_effect = lambda x: x

    with (
        patch("notebooklm_tools.cli.commands.studio.get_alias_manager", return_value=alias_mgr),
        patch("notebooklm_tools.cli.commands.studio.get_client", return_value=mock_client),
        patch(
            "notebooklm_tools.cli.commands.studio.studio_service.revise_artifact",
            side_effect=ServiceError(
                "backend rejected revision",
                user_message="Failed to revise slide deck — Google API error code 7 (PERMISSION_DENIED).",
                hint=(
                    "Verify the artifact_id points to a completed slide deck in an editable "
                    "notebook you own. NotebookLM rejects revisions for view-only/shared decks."
                ),
            ),
        ),
    ):
        result = runner.invoke(
            slides_app,
            [
                "revise",
                "art-1",
                "--slide",
                "1 Tighten the title",
                "--confirm",
            ],
        )

    assert result.exit_code == 1
    assert "PERMISSION_DENIED" in result.output
    assert "Hint:" in result.output
    assert "editable" in result.output
    assert "notebook you own" in result.output


def _status_client():
    client = MagicMock()
    client.__enter__ = lambda instance: instance
    client.__exit__ = MagicMock(return_value=False)
    return client


def _status_result():
    return {
        "artifacts": [
            {"artifact_id": "video-1", "type": "video", "status": "completed"},
            {"artifact_id": "audio-1", "type": "audio", "status": "completed"},
        ],
        "total": 2,
        "completed": 2,
        "in_progress": 0,
        "returned": 2,
        "offset": 0,
        "limit": 20,
        "has_more": False,
    }


def test_studio_status_can_emit_mcp_compatible_json(runner):
    alias_manager = MagicMock()
    alias_manager.resolve.side_effect = lambda value: value
    client = _status_client()

    with (
        patch("notebooklm_tools.cli.commands.studio.get_alias_manager", return_value=alias_manager),
        patch("notebooklm_tools.cli.commands.studio.get_client", return_value=client),
        patch(
            "notebooklm_tools.cli.commands.studio.studio_service.get_studio_status",
            return_value=_status_result(),
        ) as get_status,
    ):
        result = runner.invoke(
            app,
            ["status", "nb-1", "--json", "--mcp-compatible"],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    assert payload["artifacts"][0]["artifact_id"] == "video-1"
    assert payload["pagination"] == {
        "returned": 2,
        "offset": 0,
        "limit": 20,
        "has_more": False,
    }
    get_status.assert_called_once_with(
        client,
        "nb-1",
        artifact_id=None,
        include_details=False,
        limit=20,
        offset=0,
    )


def test_video_list_only_emits_video_artifacts(runner):
    alias_manager = MagicMock()
    alias_manager.resolve.side_effect = lambda value: value

    with (
        patch("notebooklm_tools.cli.commands.studio.get_alias_manager", return_value=alias_manager),
        patch("notebooklm_tools.cli.commands.studio.get_client", return_value=_status_client()),
        patch(
            "notebooklm_tools.cli.commands.studio.studio_service.get_studio_status",
            return_value=_status_result(),
        ),
    ):
        result = runner.invoke(video_app, ["list", "nb-1", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == [
        {
            "id": "video-1",
            "artifact_id": "video-1",
            "type": "video",
            "status": "completed",
            "custom_instructions": None,
            "visual_style_prompt": None,
        }
    ]
