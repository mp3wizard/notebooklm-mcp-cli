"""Named usage checks load only the requested account and release its client."""

from unittest.mock import patch

import pytest

from notebooklm_tools.services import usage
from notebooklm_tools.services.auth import AuthManager
from notebooklm_tools.services.errors import ServiceError


def test_profile_session_fields_and_cleanup_on_usage_failure():
    AuthManager("work").save_profile(
        cookies={"SID": "work"},
        csrf_token="csrf",
        session_id="session",
        build_label="build",
        base_host="notebook.google.com",
    )
    with (
        patch.object(usage, "NotebookLMClient") as client_type,
        patch.object(usage, "get_usage", side_effect=ServiceError("quota unavailable")),
        pytest.raises(ServiceError, match="quota unavailable"),
    ):
        usage.get_usage_for_profile("work")
    client_type.assert_called_once_with(
        cookies={"SID": "work"},
        csrf_token="csrf",
        session_id="session",
        build_label="build",
        base_host="notebook.google.com",
        profile_name="work",
    )
    client_type.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "profile",
    ["missing", "", "../personal", "/tmp/account", "..", "work/personal", "work\\personal"],
)
def test_invalid_or_missing_profile_never_constructs_a_client(profile):
    with patch.object(usage, "NotebookLMClient") as client_type, pytest.raises(ServiceError):
        usage.get_usage_for_profile(profile)
    client_type.assert_not_called()


def test_corrupt_profile_returns_service_error():
    manager = AuthManager("work")
    manager.cookies_file.write_text("not json")
    with pytest.raises(ServiceError, match="work"):
        usage.get_usage_for_profile("work")
