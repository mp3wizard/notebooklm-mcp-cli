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
            "notebooklm_tools.mcp.tools.studio.get_notebook_url",
            return_value="https://notebook.cloud.google.com/eu/notebook/nb-1?project=project-123",
        ) as get_notebook_url,
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
    assert result["notebook_url"] == (
        "https://notebook.cloud.google.com/eu/notebook/nb-1?project=project-123"
    )
    get_notebook_url.assert_called_once_with("nb-1")


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


def test_studio_create_uses_configured_notebook_url():
    mock_client = MagicMock()

    with (
        patch("notebooklm_tools.mcp.tools.studio.get_client", return_value=mock_client),
        patch(
            "notebooklm_tools.mcp.tools.studio.get_notebook_url",
            return_value="https://notebook.cloud.google.com/eu/notebook/nb-1?project=project-123",
        ) as get_notebook_url,
        patch(
            "notebooklm_tools.mcp.tools.studio._studio_auth_is_valid",
            return_value=(True, None, None),
        ),
        patch(
            "notebooklm_tools.mcp.tools.studio.studio_service.create_artifact",
            return_value={"artifact_id": "art-1"},
        ),
    ):
        result = studio.studio_create(
            notebook_id="nb-1",
            artifact_type="video",
            confirm=True,
        )

    assert result["status"] == "success"
    assert result["notebook_url"] == (
        "https://notebook.cloud.google.com/eu/notebook/nb-1?project=project-123"
    )
    get_notebook_url.assert_called_once_with("nb-1")


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


def test_studio_revise_uses_configured_notebook_url():
    mock_client = MagicMock()

    with (
        patch("notebooklm_tools.mcp.tools.studio.get_client", return_value=mock_client),
        patch(
            "notebooklm_tools.mcp.tools.studio.get_notebook_url",
            return_value="https://notebook.cloud.google.com/eu/notebook/nb-1?project=project-123",
        ) as get_notebook_url,
        patch(
            "notebooklm_tools.mcp.tools.studio.studio_service.revise_artifact",
            return_value={"artifact_id": "art-2"},
        ),
    ):
        result = studio.studio_revise(
            notebook_id="nb-1",
            artifact_id="art-1",
            slide_instructions=[{"slide": 1, "instruction": "Tighten the title"}],
            confirm=True,
        )

    assert result["status"] == "success"
    assert result["notebook_url"] == (
        "https://notebook.cloud.google.com/eu/notebook/nb-1?project=project-123"
    )
    get_notebook_url.assert_called_once_with("nb-1")


_MCP = "notebooklm_tools.mcp.tools.studio"


def test_report_rejects_unknown_action():
    result = studio.report(notebook_id="nb", artifact_id="rep", action="delete")
    assert result["status"] == "error"
    assert "get, elements, generate" in result["error"]


def test_report_get_keeps_success_envelope():
    service = {"artifact_id": "rep", "status": "completed", "parse_status": "ok", "elements": []}
    with (
        patch(f"{_MCP}.get_client", return_value=MagicMock()),
        patch(f"{_MCP}.get_notebook_url", return_value="url"),
        patch(f"{_MCP}.studio_service.get_report", return_value=service),
    ):
        result = studio.report(notebook_id="nb", artifact_id="rep", action="get")
    assert result["status"] == "success"
    assert result["artifact_status"] == "completed"
    assert result["parse_status"] == "ok"


def test_report_elements_passes_wait_and_content():
    with (
        patch(f"{_MCP}.get_client", return_value=MagicMock()),
        patch(f"{_MCP}.get_notebook_url", return_value="url"),
        patch(
            f"{_MCP}.studio_service.list_report_elements",
            return_value={"elements": [], "timed_out": False, "review_label": "L"},
        ) as lst,
    ):
        result = studio.report(
            notebook_id="nb",
            artifact_id="rep",
            action="elements",
            wait_for="a,b",
            timeout=30,
            include_content=True,
        )
    assert lst.call_args.kwargs == {
        "wait_for": ["a", "b"],
        "timeout": 30.0,
        "include_content": True,
    }
    assert result["status"] == "success" and result["review_label"] == "L"


def test_report_generate_validates_without_confirm():
    from notebooklm_tools.services.interactive_reports import PreparedElement, PreparedPlan

    prepared = PreparedPlan(
        report_id="rep",
        source_ids=["s"],
        language="en",
        elements=[
            PreparedElement(
                "el-1", "quiz", "Quiz", "prompt", {"difficulty": 3}, {"difficulty": "hard"}
            )
        ],
    )
    with (
        patch(f"{_MCP}.get_client", return_value=MagicMock()),
        patch(f"{_MCP}.studio_service.prepare_element_plan", return_value=prepared),
        patch(f"{_MCP}.studio_service.generate_report_elements") as gen,
    ):
        result = studio.report(
            notebook_id="nb",
            artifact_id="rep",
            action="generate",
            plan=[{"element_id": "el-1", "settings": {"difficulty": "hard"}}],
        )
    assert result["status"] == "pending_confirmation"
    assert result["generations_to_start"] == 1
    assert result["plan"][0]["settings"] == {"difficulty": "hard"}
    gen.assert_not_called()


def test_report_generate_runs_on_confirm_and_keeps_success_envelope():
    batch = {
        "report_id": "rep",
        "results": [
            {
                "element_id": "el-1",
                "title": "Q",
                "outcome": "failed",
                "element_status": None,
                "error": "quota",
                "error_category": "quota",
            }
        ],
        "counts": {"started": 0, "failed": 1, "unknown": 0, "not_started": 0},
        "stopped_reason": "quota",
    }
    with (
        patch(f"{_MCP}.get_client", return_value=MagicMock()),
        patch(f"{_MCP}.get_notebook_url", return_value="url"),
        patch(f"{_MCP}.studio_service.generate_report_elements", return_value=batch),
    ):
        result = studio.report(
            notebook_id="nb",
            artifact_id="rep",
            action="generate",
            plan='[{"element_id": "el-1"}]',
            confirm=True,
        )
    assert result["status"] == "success"
    assert result["stopped_reason"] == "quota"
    assert result["results"][0]["outcome"] == "failed"


def test_report_generate_requires_plan_and_rejects_bad_plan():
    with (
        patch(f"{_MCP}.get_client", return_value=MagicMock()),
        patch(f"{_MCP}.studio_service.generate_report_elements") as gen,
    ):
        missing = studio.report(
            notebook_id="nb", artifact_id="rep", action="generate", confirm=True
        )
        bad = studio.report(
            notebook_id="nb",
            artifact_id="rep",
            action="generate",
            plan='{"element_id": "x"}',
            confirm=True,
        )
    assert missing["status"] == "error" and "plan" in missing["error"]
    assert bad["status"] == "error"
    gen.assert_not_called()


def test_old_report_tools_are_gone():
    for name in (
        "report_get",
        "report_list_elements",
        "report_generate_element",
        "report_generate_elements",
    ):
        assert not hasattr(studio, name), name
