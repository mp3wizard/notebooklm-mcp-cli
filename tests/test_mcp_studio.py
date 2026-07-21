"""Unit tests for MCP studio tools."""

from unittest.mock import MagicMock, patch

from notebooklm_tools.mcp.tools import studio
from notebooklm_tools.services.errors import ServiceError


def _status_result(artifacts):
    return {
        "artifacts": artifacts,
        "total": 64,
        "completed": 60,
        "in_progress": 4,
        "returned": len(artifacts),
        "offset": 0,
        "limit": 20,
        "has_more": True,
    }


def test_studio_status_is_lean_and_bounded_by_default():
    mock_client = MagicMock()
    service_result = _status_result(
        [{"artifact_id": "art-1", "type": "video", "status": "in_progress"}]
    )

    with (
        patch("notebooklm_tools.mcp.tools.studio.get_client", return_value=mock_client),
        patch(
            "notebooklm_tools.mcp.tools.studio.studio_service.get_studio_status",
            return_value=service_result,
        ) as get_status,
    ):
        result = studio.studio_status(notebook_id="nb-1")

    get_status.assert_called_once_with(
        mock_client,
        "nb-1",
        artifact_id=None,
        include_details=False,
        limit=20,
        offset=0,
    )
    assert result["artifacts"] == service_result["artifacts"]
    assert result["pagination"] == {
        "returned": 1,
        "offset": 0,
        "limit": 20,
        "has_more": True,
    }


def test_studio_status_can_request_one_detailed_artifact():
    mock_client = MagicMock()
    service_result = _status_result(
        [{"artifact_id": "art-1", "custom_instructions": "Exact prompt"}]
    )
    service_result.update({"limit": 1, "has_more": False})

    with (
        patch("notebooklm_tools.mcp.tools.studio.get_client", return_value=mock_client),
        patch(
            "notebooklm_tools.mcp.tools.studio.studio_service.get_studio_status",
            return_value=service_result,
        ) as get_status,
    ):
        result = studio.studio_status(
            notebook_id="nb-1",
            artifact_id="art-1",
            include_details=True,
        )

    get_status.assert_called_once_with(
        mock_client,
        "nb-1",
        artifact_id="art-1",
        include_details=True,
        limit=20,
        offset=0,
    )
    assert result["artifacts"][0]["custom_instructions"] == "Exact prompt"


def test_studio_create_preserves_rate_limit_hint():
    mock_client = MagicMock()
    rate_limit = ServiceError(
        "rate limited",
        user_message="Rate limited — wait before retrying video creation.",
        hint="Wait 1-2 minutes and try again.",
    )

    with (
        patch("notebooklm_tools.mcp.tools.studio.get_client", return_value=mock_client),
        patch(
            "notebooklm_tools.mcp.tools.studio._studio_auth_is_valid",
            return_value=(True, None, None),
        ),
        patch(
            "notebooklm_tools.mcp.tools.studio.studio_service.create_artifact",
            side_effect=rate_limit,
        ),
    ):
        result = studio.studio_create(
            notebook_id="nb-1",
            artifact_type="video",
            confirm=True,
        )

    assert result["status"] == "error"
    assert result["hint"] == "Wait 1-2 minutes and try again."


def test_studio_revise_preserves_hint_on_service_error():
    mock_client = MagicMock()

    with (
        patch("notebooklm_tools.mcp.tools.studio.get_client", return_value=mock_client),
        patch(
            "notebooklm_tools.mcp.tools.studio.studio_service.revise_artifact",
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
        result = studio.studio_revise(
            notebook_id="nb-1",
            artifact_id="art-1",
            slide_instructions=[{"slide": 1, "instruction": "Tighten the title"}],
            confirm=True,
        )

    assert result["status"] == "error"
    assert "PERMISSION_DENIED" in result["error"]
    assert "editable notebook you own" in result["hint"]
