"""Tests for services.sharing module."""

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from notebooklm_tools.core.errors import RPCError
from notebooklm_tools.services.errors import ServiceError, ValidationError
from notebooklm_tools.services.sharing import (
    get_share_status,
    invite_collaborator,
    invite_collaborators_bulk,
    set_public_access,
)


@dataclass
class MockCollaborator:
    email: str
    role: str
    is_pending: bool = False
    display_name: str | None = None


@dataclass
class MockShareStatus:
    is_public: bool
    access_level: str
    collaborators: list
    public_link: str | None = None


@pytest.fixture
def mock_client():
    return MagicMock()


class TestGetShareStatus:
    """Test get_share_status service function."""

    def test_returns_correct_structure(self, mock_client):
        mock_client.get_share_status.return_value = MockShareStatus(
            is_public=True,
            access_level="public",
            collaborators=[
                MockCollaborator(email="alice@example.com", role="owner"),
                MockCollaborator(email="bob@example.com", role="editor", is_pending=True),
            ],
            public_link="https://notebooklm.google.com/notebook/abc123",
        )

        result = get_share_status(mock_client, "nb-123")

        assert result["notebook_id"] == "nb-123"
        assert result["is_public"] is True
        assert result["access_level"] == "public"
        assert result["public_link"] == "https://notebooklm.google.com/notebook/abc123"
        assert result["collaborator_count"] == 2
        assert len(result["collaborators"]) == 2

    def test_collaborator_details_preserved(self, mock_client):
        mock_client.get_share_status.return_value = MockShareStatus(
            is_public=False,
            access_level="restricted",
            collaborators=[
                MockCollaborator(
                    email="alice@example.com",
                    role="owner",
                    is_pending=False,
                    display_name="Alice",
                ),
            ],
        )

        result = get_share_status(mock_client, "nb-123")
        collab = result["collaborators"][0]

        assert collab["email"] == "alice@example.com"
        assert collab["role"] == "owner"
        assert collab["is_pending"] is False
        assert collab["display_name"] == "Alice"

    def test_empty_collaborators(self, mock_client):
        mock_client.get_share_status.return_value = MockShareStatus(
            is_public=False,
            access_level="restricted",
            collaborators=[],
        )

        result = get_share_status(mock_client, "nb-123")
        assert result["collaborators"] == []
        assert result["collaborator_count"] == 0

    def test_api_error_raises_service_error(self, mock_client):
        mock_client.get_share_status.side_effect = RuntimeError("API error")
        with pytest.raises(ServiceError, match="Failed to get share status"):
            get_share_status(mock_client, "nb-123")


class TestSetPublicAccess:
    """Test set_public_access service function."""

    def test_enable_public_returns_link(self, mock_client):
        mock_client.set_public_access.return_value = "https://notebooklm.google.com/notebook/abc123"

        result = set_public_access(mock_client, "nb-123", is_public=True)

        assert result["is_public"] is True
        assert result["public_link"] == "https://notebooklm.google.com/notebook/abc123"
        assert "enabled" in result["message"].lower()

    def test_disable_public_returns_none_link(self, mock_client):
        mock_client.set_public_access.return_value = None

        result = set_public_access(mock_client, "nb-123", is_public=False)

        assert result["is_public"] is False
        assert result["public_link"] is None
        assert "disabled" in result["message"].lower()

    def test_api_error_raises_service_error(self, mock_client):
        mock_client.set_public_access.side_effect = RuntimeError("API error")
        with pytest.raises(ServiceError, match="Failed to set public access"):
            set_public_access(mock_client, "nb-123", is_public=True)


class TestInviteCollaborator:
    """Test invite_collaborator service function."""

    def test_valid_viewer_role(self, mock_client):
        mock_client.add_collaborator.return_value = True

        result = invite_collaborator(mock_client, "nb-123", "alice@example.com", "viewer")

        assert result["email"] == "alice@example.com"
        assert result["role"] == "viewer"
        assert "Invited" in result["message"]

    def test_valid_editor_role(self, mock_client):
        mock_client.add_collaborator.return_value = True

        result = invite_collaborator(mock_client, "nb-123", "bob@example.com", "editor")

        assert result["role"] == "editor"

    def test_invalid_role_raises_validation_error(self, mock_client):
        with pytest.raises(ValidationError, match="Invalid role"):
            invite_collaborator(mock_client, "nb-123", "alice@example.com", "admin")

    def test_role_case_insensitive(self, mock_client):
        mock_client.add_collaborator.return_value = True

        result = invite_collaborator(mock_client, "nb-123", "alice@example.com", "VIEWER")
        assert result["role"] == "viewer"

    def test_falsy_result_raises_service_error(self, mock_client):
        mock_client.add_collaborator.return_value = None

        with pytest.raises(ServiceError, match="falsy result"):
            invite_collaborator(mock_client, "nb-123", "alice@example.com", "viewer")

    def test_api_error_raises_service_error(self, mock_client):
        mock_client.add_collaborator.side_effect = RuntimeError("API error")
        with pytest.raises(ServiceError, match="Failed to invite"):
            invite_collaborator(mock_client, "nb-123", "alice@example.com", "viewer")

    def test_permission_denied_explains_uncertain_cause(self, mock_client):
        mock_client.add_collaborator.side_effect = RPCError(
            "API error (code 7): type.googleapis.com/google.rpc.ErrorInfo",
            error_code=7,
            detail_type="type.googleapis.com/google.rpc.ErrorInfo",
        )

        with pytest.raises(ServiceError) as exc_info:
            invite_collaborator(mock_client, "nb-123", "alice@example.com", "viewer")

        error = exc_info.value
        assert "Google denied the invitation" in error.user_message
        assert "permission" in error.user_message.lower()
        assert "may" in error.hint.lower()
        assert "public link" not in error.hint.lower()


class TestBulkInviteCollaborators:
    """Test invite_collaborators_bulk service function."""

    def test_valid_bulk_invite(self, mock_client):
        mock_client.add_collaborators_bulk.return_value = True

        recipients = [
            {"email": "alice@example.com", "role": "viewer"},
            {"email": "bob@example.com", "role": "editor"},
        ]
        result = invite_collaborators_bulk(mock_client, "nb-123", recipients)

        assert result["notebook_id"] == "nb-123"
        assert result["invited_count"] == 2
        assert len(result["recipients"]) == 2
        assert result["recipients"][0]["email"] == "alice@example.com"
        assert result["recipients"][1]["role"] == "editor"
        assert "2 collaborators" in result["message"]

    def test_default_role_is_viewer(self, mock_client):
        mock_client.add_collaborators_bulk.return_value = True

        recipients = [{"email": "alice@example.com"}]
        result = invite_collaborators_bulk(mock_client, "nb-123", recipients)

        assert result["recipients"][0]["role"] == "viewer"

    def test_empty_recipients_raises_validation_error(self, mock_client):
        with pytest.raises(ValidationError):
            invite_collaborators_bulk(mock_client, "nb-123", [])

    def test_invalid_role_raises_validation_error(self, mock_client):
        recipients = [
            {"email": "alice@example.com", "role": "admin"},
        ]
        with pytest.raises(ValidationError, match="Invalid role"):
            invite_collaborators_bulk(mock_client, "nb-123", recipients)

    def test_empty_email_raises_validation_error(self, mock_client):
        recipients = [{"email": "", "role": "viewer"}]
        with pytest.raises(ValidationError, match="Empty email"):
            invite_collaborators_bulk(mock_client, "nb-123", recipients)

    def test_falsy_result_raises_service_error(self, mock_client):
        mock_client.add_collaborators_bulk.return_value = None

        recipients = [{"email": "alice@example.com", "role": "viewer"}]
        with pytest.raises(ServiceError, match="falsy result"):
            invite_collaborators_bulk(mock_client, "nb-123", recipients)

    def test_api_error_raises_service_error(self, mock_client):
        mock_client.add_collaborators_bulk.side_effect = RuntimeError("API error")

        recipients = [{"email": "alice@example.com", "role": "viewer"}]
        with pytest.raises(ServiceError, match="Failed to invite collaborators"):
            invite_collaborators_bulk(mock_client, "nb-123", recipients)

    def test_permission_denied_explains_uncertain_cause(self, mock_client):
        mock_client.add_collaborators_bulk.side_effect = RPCError(
            "API error (code 7): type.googleapis.com/google.rpc.ErrorInfo", error_code=7
        )

        with pytest.raises(ServiceError) as exc_info:
            invite_collaborators_bulk(
                mock_client, "nb-123", [{"email": "alice@example.com", "role": "viewer"}]
            )

        assert "Google denied the invitation" in exc_info.value.user_message
        assert exc_info.value.provider_code == 7
