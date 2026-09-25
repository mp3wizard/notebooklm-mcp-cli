"""Tests for Studio CLI commands."""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from notebooklm_tools.cli.commands.studio import app, report_app, slides_app, video_app
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
            "notebooklm_tools.cli.commands.studio.get_notebook_url",
            return_value="https://notebook.cloud.google.com/eu/notebook/nb-1?project=project-123",
        ) as get_notebook_url,
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
    assert payload["notebook_url"] == (
        "https://notebook.cloud.google.com/eu/notebook/nb-1?project=project-123"
    )
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
    get_notebook_url.assert_called_once_with("nb-1")


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


def _cli_client():
    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    alias_mgr = MagicMock()
    alias_mgr.resolve.side_effect = lambda x: x
    return mock_client, alias_mgr


def test_element_create_parses_settings(runner):
    client, aliases = _cli_client()
    with (
        patch("notebooklm_tools.cli.commands.studio.get_alias_manager", return_value=aliases),
        patch("notebooklm_tools.cli.commands.studio.get_client", return_value=client),
        patch(
            "notebooklm_tools.cli.commands.studio.studio_service.generate_report_element",
            return_value={
                "report_id": "r",
                "element_id": "e",
                "title": "T",
                "outcome": "started",
                "element_status": "queued",
                "message": "ok",
            },
        ) as gen,
    ):
        result = runner.invoke(
            report_app,
            [
                "element",
                "create",
                "nb",
                "r",
                "--type",
                "quiz",
                "--setting",
                "difficulty=hard",
                "--setting",
                "question_amount=more",
                "--confirm",
            ],
        )
    assert result.exit_code == 0, result.output
    assert gen.call_args.kwargs["settings"] == {"difficulty": "hard", "question_amount": "more"}


def test_element_create_rejects_malformed_setting(runner):
    result = runner.invoke(
        report_app,
        ["element", "create", "nb", "r", "--type", "quiz", "--setting", "hard", "--confirm"],
    )
    assert result.exit_code != 0
    assert "name=value" in result.output


def test_create_batch_rejects_bad_plan_file_before_network(runner, tmp_path):
    bad = tmp_path / "plan.json"
    bad.write_text("not json")
    client, aliases = _cli_client()
    with (
        patch("notebooklm_tools.cli.commands.studio.get_alias_manager", return_value=aliases),
        patch("notebooklm_tools.cli.commands.studio.get_client", return_value=client) as gc,
    ):
        result = runner.invoke(
            report_app, ["element", "create-batch", "nb", "r", "--plan", str(bad), "--confirm"]
        )
    assert result.exit_code != 0
    gc.assert_not_called()


def test_create_batch_runs_plan(runner, tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps([{"element_id": "e1"}, {"element_id": "e2", "settings": {"difficulty": "easy"}}])
    )
    client, aliases = _cli_client()
    batch = {
        "report_id": "r",
        "results": [
            {
                "element_id": "e1",
                "title": "A",
                "outcome": "started",
                "element_status": "queued",
                "error": None,
                "error_category": None,
            },
            {
                "element_id": "e2",
                "title": "B",
                "outcome": "unknown",
                "element_status": None,
                "error": "lost",
                "error_category": "unknown_outcome",
            },
        ],
        "counts": {"started": 1, "failed": 0, "unknown": 1, "not_started": 0},
        "stopped_reason": None,
    }
    with (
        patch("notebooklm_tools.cli.commands.studio.get_alias_manager", return_value=aliases),
        patch("notebooklm_tools.cli.commands.studio.get_client", return_value=client),
        patch(
            "notebooklm_tools.cli.commands.studio.studio_service.generate_report_elements",
            return_value=batch,
        ) as gen,
    ):
        result = runner.invoke(
            report_app,
            ["element", "create-batch", "nb", "r", "--plan", str(plan), "--confirm", "--json"],
        )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["counts"]["unknown"] == 1
    assert gen.call_args.args[3][1]["settings"] == {"difficulty": "easy"}


def test_elements_wait_passes_ids(runner):
    client, aliases = _cli_client()
    with (
        patch("notebooklm_tools.cli.commands.studio.get_alias_manager", return_value=aliases),
        patch("notebooklm_tools.cli.commands.studio.get_client", return_value=client),
        patch(
            "notebooklm_tools.cli.commands.studio.studio_service.list_report_elements",
            return_value={"elements": [], "timed_out": False, "review_label": None},
        ) as lst,
    ):
        result = runner.invoke(
            report_app,
            [
                "elements",
                "nb",
                "r",
                "--wait",
                "e1",
                "--wait",
                "e2",
                "--timeout",
                "60",
                "--json",
            ],
        )
    assert result.exit_code == 0, result.output
    assert lst.call_args.kwargs["wait_for"] == ["e1", "e2"]
    assert lst.call_args.kwargs["timeout"] == 60.0
