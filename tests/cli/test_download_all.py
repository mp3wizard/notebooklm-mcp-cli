"""Tests for the `nlm download all` CLI command."""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from notebooklm_tools.cli.commands.download import app
from notebooklm_tools.services.errors import ServiceError


@pytest.fixture
def runner():
    return CliRunner()


def _single_result(**overrides):
    result = {
        "notebook_id": "nb-1",
        "notebook_title": "My Notebook",
        "output_dir": "/tmp/exports/My Notebook",
        "items": [
            {
                "artifact_id": "art-1",
                "artifact_type": "report",
                "title": "Report",
                "path": "/tmp/exports/My Notebook/Report.md",
                "success": True,
                "error": None,
            }
        ],
        "skipped": [],
        "total_artifacts": 1,
        "downloaded": 1,
        "failed": 0,
    }
    result.update(overrides)
    return result


def _sweep_result(**overrides):
    result = {
        "output_dir": "/tmp/exports",
        "notebooks": [
            {
                "notebook_id": "nb-1",
                "notebook_title": "My Notebook",
                "output_dir": "/tmp/exports/My Notebook",
                "downloaded": 1,
                "failed": 0,
                "skipped": 0,
                "error": None,
            }
        ],
        "total_notebooks": 1,
        "downloaded": 1,
        "failed": 0,
        "errored_notebooks": 0,
    }
    result.update(overrides)
    return result


def _alias_manager():
    alias_mgr = MagicMock()
    alias_mgr.resolve.side_effect = lambda x: x
    return alias_mgr


def test_requires_notebook_id_or_all_notebooks_flag(runner):
    result = runner.invoke(app, ["all"])

    assert result.exit_code == 1
    assert "Provide either a notebook ID or --all-notebooks" in result.output


def test_rejects_both_notebook_id_and_all_notebooks(runner):
    result = runner.invoke(app, ["all", "nb-1", "--all-notebooks"])

    assert result.exit_code == 1
    assert "not both" in result.output


def test_single_notebook_human_output(runner):
    with (
        patch("notebooklm_tools.cli.commands.download.get_client", return_value=MagicMock()),
        patch(
            "notebooklm_tools.cli.commands.download.get_alias_manager",
            return_value=_alias_manager(),
        ),
        patch(
            "notebooklm_tools.services.downloads.download_all",
            return_value=_single_result(),
        ),
    ):
        result = runner.invoke(app, ["all", "nb-1", "--no-progress"])

    assert result.exit_code == 0
    assert "My Notebook" in result.output
    assert "1" in result.output
    assert "downloaded" in result.output


def test_single_notebook_json_output(runner):
    service_result = _single_result()

    with (
        patch("notebooklm_tools.cli.commands.download.get_client", return_value=MagicMock()),
        patch(
            "notebooklm_tools.cli.commands.download.get_alias_manager",
            return_value=_alias_manager(),
        ),
        patch(
            "notebooklm_tools.services.downloads.download_all",
            return_value=service_result,
        ),
    ):
        result = runner.invoke(app, ["all", "nb-1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["downloaded"] == 1
    assert payload["notebook_title"] == "My Notebook"


def test_all_notebooks_sweep_routes_to_service(runner):
    with (
        patch("notebooklm_tools.cli.commands.download.get_client", return_value=MagicMock()),
        patch(
            "notebooklm_tools.services.downloads.download_all_notebooks",
            return_value=_sweep_result(),
        ) as mock_sweep,
    ):
        result = runner.invoke(app, ["all", "--all-notebooks", "--skip-existing", "--no-progress"])

    assert result.exit_code == 0
    assert mock_sweep.call_args.kwargs["skip_existing"] is True
    assert "My Notebook" in result.output
    assert "notebooks" in result.output


def test_exit_code_1_when_nothing_downloaded_and_failures_occurred(runner):
    service_result = _single_result(downloaded=0, failed=2, items=[])

    with (
        patch("notebooklm_tools.cli.commands.download.get_client", return_value=MagicMock()),
        patch(
            "notebooklm_tools.cli.commands.download.get_alias_manager",
            return_value=_alias_manager(),
        ),
        patch(
            "notebooklm_tools.services.downloads.download_all",
            return_value=service_result,
        ),
    ):
        result = runner.invoke(app, ["all", "nb-1", "--no-progress"])

    assert result.exit_code == 1


def test_exit_code_0_on_partial_success(runner):
    service_result = _single_result(downloaded=1, failed=1)

    with (
        patch("notebooklm_tools.cli.commands.download.get_client", return_value=MagicMock()),
        patch(
            "notebooklm_tools.cli.commands.download.get_alias_manager",
            return_value=_alias_manager(),
        ),
        patch(
            "notebooklm_tools.services.downloads.download_all",
            return_value=service_result,
        ),
    ):
        result = runner.invoke(app, ["all", "nb-1", "--no-progress"])

    assert result.exit_code == 0


def test_service_error_reports_hint_and_exits_1(runner):
    with (
        patch("notebooklm_tools.cli.commands.download.get_client", return_value=MagicMock()),
        patch(
            "notebooklm_tools.cli.commands.download.get_alias_manager",
            return_value=_alias_manager(),
        ),
        patch(
            "notebooklm_tools.services.downloads.download_all",
            side_effect=ServiceError(
                "boom", user_message="Notebook not found.", hint="Check the ID."
            ),
        ),
    ):
        result = runner.invoke(app, ["all", "nb-1", "--no-progress"])

    assert result.exit_code == 1
    assert "Notebook not found." in result.output


def test_types_filter_is_parsed_and_passed_through(runner):
    with (
        patch("notebooklm_tools.cli.commands.download.get_client", return_value=MagicMock()),
        patch(
            "notebooklm_tools.cli.commands.download.get_alias_manager",
            return_value=_alias_manager(),
        ),
        patch(
            "notebooklm_tools.services.downloads.download_all",
            return_value=_single_result(),
        ) as mock_download_all,
    ):
        runner.invoke(app, ["all", "nb-1", "--types", "video, report", "--no-progress"])

    assert mock_download_all.call_args.kwargs["artifact_types"] == ["video", "report"]
