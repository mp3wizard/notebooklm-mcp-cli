"""JSON output parity for mutating CLI commands."""

import inspect
import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from notebooklm_tools.cli.commands import notebook, source, studio, verbs


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.__enter__ = lambda s: s
    client.__exit__ = MagicMock(return_value=False)
    return client


def _identity_alias():
    manager = MagicMock()
    manager.resolve.side_effect = lambda value: value
    return manager


@pytest.mark.parametrize(
    "command",
    [
        studio.create_audio,
        studio.create_video,
        studio.create_report,
        studio.create_infographic,
        studio.create_slides,
        studio.create_quiz,
        studio.create_flashcards,
        studio.create_data_table,
        studio.create_mindmap,
        verbs.create_audio_verb,
        verbs.create_video_verb,
        verbs.create_report_verb,
        verbs.create_infographic_verb,
        verbs.create_slides_verb,
        verbs.create_quiz_verb,
        verbs.create_flashcards_verb,
        verbs.create_data_table_verb,
        verbs.create_mindmap_verb,
    ],
)
def test_all_studio_create_commands_accept_json(command):
    assert "json_output" in inspect.signature(command).parameters


def test_source_add_single_json_is_machine_parseable(runner, mock_client):
    service_result = {"source_type": "url", "source_id": "src-1", "title": "Example"}
    with (
        patch(
            "notebooklm_tools.cli.commands.source.get_alias_manager", return_value=_identity_alias()
        ),
        patch("notebooklm_tools.cli.commands.source.get_client", return_value=mock_client),
        patch(
            "notebooklm_tools.cli.commands.source.sources_service.add_source",
            return_value=service_result,
        ),
    ):
        result = runner.invoke(
            source.app,
            ["add", "nb-1", "--url", "https://example.com", "--json"],
        )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == service_result


def test_source_add_bulk_json_is_machine_parseable(runner, mock_client):
    service_result = {
        "results": [
            {"source_type": "url", "source_id": "src-1", "title": "One"},
            {"source_type": "url", "source_id": "src-2", "title": "Two"},
        ],
        "added_count": 2,
    }
    with (
        patch(
            "notebooklm_tools.cli.commands.source.get_alias_manager", return_value=_identity_alias()
        ),
        patch("notebooklm_tools.cli.commands.source.get_client", return_value=mock_client),
        patch(
            "notebooklm_tools.cli.commands.source.sources_service.add_sources",
            return_value=service_result,
        ),
    ):
        result = runner.invoke(
            source.app,
            [
                "add",
                "nb-1",
                "--url",
                "https://one.example",
                "--url",
                "https://two.example",
                "--json",
            ],
        )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == service_result


def test_source_delete_json_reports_deleted_ids(runner, mock_client):
    with (
        patch(
            "notebooklm_tools.cli.commands.source.get_alias_manager", return_value=_identity_alias()
        ),
        patch("notebooklm_tools.cli.commands.source.get_client", return_value=mock_client),
        patch("notebooklm_tools.cli.commands.source.sources_service.delete_sources"),
    ):
        result = runner.invoke(
            source.app,
            ["delete", "src-1", "src-2", "--confirm", "--json"],
        )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "status": "success",
        "deleted_source_ids": ["src-1", "src-2"],
        "deleted_count": 2,
    }


def test_notebook_delete_json_reports_deleted_id(runner, mock_client):
    service_result = {"message": "Notebook nb-1 has been permanently deleted."}
    with (
        patch(
            "notebooklm_tools.cli.commands.notebook.get_alias_manager",
            return_value=_identity_alias(),
        ),
        patch("notebooklm_tools.cli.commands.notebook.get_client", return_value=mock_client),
        patch(
            "notebooklm_tools.cli.commands.notebook.notebooks_service.delete_notebook",
            return_value=service_result,
        ),
    ):
        result = runner.invoke(
            notebook.app,
            ["delete", "nb-1", "--confirm", "--json"],
        )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == service_result


def test_shared_studio_create_json_is_machine_parseable(runner, mock_client):
    service_result = {
        "artifact_type": "audio",
        "artifact_id": "art-1",
        "status": "in_progress",
        "message": "Audio generation started.",
    }
    with (
        patch(
            "notebooklm_tools.cli.commands.studio.get_alias_manager", return_value=_identity_alias()
        ),
        patch("notebooklm_tools.cli.commands.studio.get_client", return_value=mock_client),
        patch(
            "notebooklm_tools.cli.commands.studio.studio_service.create_artifact",
            return_value=service_result,
        ),
    ):
        result = runner.invoke(
            studio.audio_app,
            ["nb-1", "--confirm", "--json"],
        )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == service_result


def test_quiz_create_json_is_machine_parseable(runner, mock_client):
    mock_client.create_quiz.return_value = {
        "artifact_id": "quiz-1",
        "status": "in_progress",
    }
    with (
        patch(
            "notebooklm_tools.cli.commands.studio.get_alias_manager", return_value=_identity_alias()
        ),
        patch("notebooklm_tools.cli.commands.studio.get_client", return_value=mock_client),
    ):
        result = runner.invoke(
            studio.quiz_app,
            ["nb-1", "--confirm", "--json"],
        )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "artifact_type": "quiz",
        "artifact_id": "quiz-1",
        "status": "in_progress",
        "message": "Quiz generation started.",
    }


def test_quiz_create_json_failure_is_machine_parseable(runner, mock_client):
    mock_client.create_quiz.return_value = None
    with (
        patch(
            "notebooklm_tools.cli.commands.studio.get_alias_manager", return_value=_identity_alias()
        ),
        patch("notebooklm_tools.cli.commands.studio.get_client", return_value=mock_client),
    ):
        result = runner.invoke(
            studio.quiz_app,
            ["nb-1", "--confirm", "--json"],
        )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert "rejected" in payload["error"]
