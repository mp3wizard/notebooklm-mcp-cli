"""Agent-facing sharing errors preserve useful provider context."""

from unittest.mock import MagicMock, patch

from notebooklm_tools.mcp.tools import sharing
from notebooklm_tools.services.errors import ServiceError


def test_invite_permission_denied_has_actionable_hint_and_code():
    error = ServiceError(
        "raw Google error",
        user_message="Google denied the invitation (permission denied).",
        hint="The cause may be an account sharing restriction.",
        category="permission_denied",
        provider_code=7,
        retryable=False,
    )
    with (
        patch.object(sharing, "get_client", return_value=MagicMock()),
        patch.object(sharing.sharing_service, "invite_collaborator", side_effect=error),
    ):
        result = sharing.notebook_share_invite("nb-1", "person@example.com")

    assert result["status"] == "error"
    assert result["hint"] == error.hint
    assert result["error_details"]["provider_code"] == 7
    assert result["error_details"]["retryable"] is False
