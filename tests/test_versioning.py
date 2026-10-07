"""Tests for shared package-version comparison semantics."""

from unittest.mock import patch

import pytest

from notebooklm_tools.cli import utils as cli_utils
from notebooklm_tools.mcp.tools import server as server_tools
from notebooklm_tools.utils.versioning import is_newer_version


@pytest.mark.parametrize(
    ("current", "latest", "expected"),
    [
        ("1.0.0", "1.0.1", True),
        ("1.0.0", "1.0.0", False),
        ("1.0.0rc1", "1.0.0", True),
        ("1.0.0", "1.0.1rc1", True),
        ("1.0.1", "1.0.1rc1", False),
        ("1.0.0.dev1", "1.0.0", True),
        ("1.0.0+local", "1.0.0", False),
        ("1!1.0.0", "2.0.0", False),
        ("not-a-version", "1.0.0", False),
        ("1.0.0", "also-invalid", False),
    ],
)
def test_is_newer_version_uses_pep440(current, latest, expected):
    assert is_newer_version(current, latest) is expected


def test_cli_update_check_handles_prerelease_current(monkeypatch):
    monkeypatch.setattr(cli_utils, "__version__", "2.0.0rc1")
    monkeypatch.setattr(
        cli_utils,
        "_get_cached_version_info",
        lambda: {"latest_version": "2.0.0"},
    )

    assert cli_utils.check_for_updates() == (True, "2.0.0")


def test_server_info_handles_prerelease_current(monkeypatch):
    monkeypatch.setattr(server_tools, "__version__", "2.0.0rc1")
    monkeypatch.setattr(server_tools, "_get_latest_pypi_version", lambda: "2.0.0")
    monkeypatch.setattr(server_tools, "_check_auth_status", lambda: "configured")
    monkeypatch.setattr(server_tools, "_check_storage_warning", lambda: None)
    monkeypatch.setattr(server_tools, "_profile_summary", lambda: {})

    with patch(
        "notebooklm_tools.mcp.tools.server._runtime_capabilities",
        return_value={"schema_version": 1},
    ):
        result = server_tools.server_info()

    assert result["latest_version"] == "2.0.0"
    assert result["update_available"] is True
