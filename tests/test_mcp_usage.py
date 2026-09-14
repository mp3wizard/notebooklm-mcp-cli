"""Profile selection must not switch the MCP server's shared account."""

from unittest.mock import MagicMock, patch

from notebooklm_tools.mcp.tools import _utils, usage
from notebooklm_tools.services.auth import AuthManager
from notebooklm_tools.utils.config import get_config


def test_named_usage_profiles_are_isolated_and_closed(monkeypatch):
    for profile in ("work", "personal"):
        AuthManager(profile).save_profile(cookies={"SID": profile}, csrf_token=f"{profile}-csrf")
    monkeypatch.setenv("NOTEBOOKLM_COOKIES", "SID=environment")
    shared_client = MagicMock()
    monkeypatch.setattr(_utils, "_client", shared_client)
    default_profile = get_config().auth.default_profile
    clients = []

    def read_usage(client):
        clients.append(client)
        return {"windows": [], "tier": client.cookies["SID"]}

    with (
        patch("notebooklm_tools.services.usage.get_usage", side_effect=read_usage),
        patch("notebooklm_tools.core.client.NotebookLMClient.close") as close,
    ):
        assert usage.usage_get(profile="work")["tier"] == "work"
        assert usage.usage_get(profile="personal")["tier"] == "personal"
    assert [client._profile_name for client in clients] == ["work", "personal"]
    assert close.call_count == 2
    assert _utils._client is shared_client
    assert get_config().auth.default_profile == default_profile


def test_missing_profile_returns_error_without_using_shared_client(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_COOKIES", "SID=environment")
    with patch.object(usage, "get_client") as shared:
        result = usage.usage_get(profile="missing")
    assert result["status"] == "error"
    assert "missing" in result["error"]
    shared.assert_not_called()


def test_default_usage_preserves_shared_client():
    with (
        patch.object(usage, "get_client") as shared,
        patch(
            "notebooklm_tools.services.usage.get_usage", return_value={"windows": [], "tier": None}
        ) as read,
    ):
        assert usage.usage_get()["status"] == "success"
    read.assert_called_once_with(shared.return_value)
    shared.return_value.close.assert_not_called()
