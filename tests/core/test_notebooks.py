"""Tests for NotebookMixin class."""

from unittest.mock import MagicMock, patch

import pytest


def test_notebook_mixin_import():
    """Test that NotebookMixin can be imported."""
    from notebooklm_tools.core.notebooks import NotebookMixin

    assert NotebookMixin is not None


def test_notebook_mixin_inherits_base():
    """Test that NotebookMixin inherits from BaseClient."""
    from notebooklm_tools.core.base import BaseClient
    from notebooklm_tools.core.notebooks import NotebookMixin

    assert issubclass(NotebookMixin, BaseClient)


def test_notebook_mixin_has_methods():
    """Test that NotebookMixin has all expected methods."""
    from notebooklm_tools.core.notebooks import NotebookMixin

    expected_methods = [
        "list_notebooks",
        "get_notebook",
        "get_notebook_summary",
        "create_notebook",
        "rename_notebook",
        "configure_chat",
        "delete_notebook",
    ]

    for method_name in expected_methods:
        assert hasattr(NotebookMixin, method_name), f"Missing method: {method_name}"


def test_enterprise_list_does_not_fallback_to_consumer_rpc():
    """Enterprise failures must remain visible instead of hiding behind a consumer call."""
    from notebooklm_tools.core.notebooks import NotebookMixin

    mixin = NotebookMixin(cookies={"SID": "x"}, csrf_token="csrf")
    mixin._is_enterprise = lambda: True
    mixin._enterprise_project_id = "project-123"
    with (
        patch.object(mixin, "_call_rpc", side_effect=RuntimeError("enterprise RPC failed")) as rpc,
        pytest.raises(RuntimeError, match="enterprise RPC failed"),
    ):
        mixin.list_notebooks()

    rpc.assert_called_once_with(
        mixin.RPC_LIST_NOTEBOOKS_ENTERPRISE,
        ["projects/project-123/locations/global", None, None, 1],
    )


def test_list_notebooks_uses_correct_rpc():
    """Test that list_notebooks calls the correct RPC."""
    from notebooklm_tools.core.notebooks import NotebookMixin

    with patch.object(NotebookMixin, "_refresh_auth_tokens"):  # noqa: SIM117
        with patch.object(NotebookMixin, "_get_client") as mock_get_client:
            with patch.object(NotebookMixin, "_build_request_body") as mock_build_body:
                with patch.object(NotebookMixin, "_build_url"):
                    with patch.object(NotebookMixin, "_parse_response"):
                        with patch.object(NotebookMixin, "_extract_rpc_result") as mock_extract:
                            # Setup mocks
                            mock_client = MagicMock()
                            mock_client.post.return_value = MagicMock(text="", status_code=200)
                            mock_get_client.return_value = mock_client
                            mock_extract.return_value = []

                            mixin = NotebookMixin(cookies={"test": "cookie"}, csrf_token="test")
                            mixin.list_notebooks()

                            # Verify correct RPC ID was used
                            mock_build_body.assert_called_once()
                            assert mock_build_body.call_args[0][0] == "wXbhsf"  # RPC_LIST_NOTEBOOKS


def test_list_notebooks_preserves_emoji():
    """Notebook emoji metadata should survive parsing into the Notebook model."""
    from notebooklm_tools.core.notebooks import NotebookMixin

    raw = [["My Notebook", [], "nb-123", "📚"]]
    with (
        patch.object(NotebookMixin, "_refresh_auth_tokens"),
        patch.object(NotebookMixin, "_call_rpc", return_value=[raw]),
    ):
        mixin = NotebookMixin(cookies={"test": "cookie"}, csrf_token="test")
        notebooks = mixin.list_notebooks()

    assert notebooks[0].emoji == "📚"


def test_create_notebook_uses_correct_rpc():
    """Test that create_notebook calls the correct RPC."""
    from notebooklm_tools.core.notebooks import NotebookMixin

    with patch.object(NotebookMixin, "_refresh_auth_tokens"):  # noqa: SIM117
        with patch.object(NotebookMixin, "_call_rpc") as mock_rpc:
            mock_rpc.return_value = ["title", None, "notebook_id_123"]

            mixin = NotebookMixin(cookies={"test": "cookie"}, csrf_token="test")
            mixin.create_notebook("Test Notebook")

            mock_rpc.assert_called_once()
            call_args = mock_rpc.call_args
            assert call_args[0][0] == "CCqFvf"  # RPC_CREATE_NOTEBOOK


def test_delete_notebook_uses_correct_rpc():
    """Test that delete_notebook calls the correct RPC."""
    from notebooklm_tools.core.notebooks import NotebookMixin

    with patch.object(NotebookMixin, "_refresh_auth_tokens"):  # noqa: SIM117
        with patch.object(NotebookMixin, "_get_client") as mock_get_client:
            with patch.object(NotebookMixin, "_build_request_body") as mock_build_body:
                with patch.object(NotebookMixin, "_build_url"):
                    with patch.object(NotebookMixin, "_parse_response"):
                        with patch.object(NotebookMixin, "_extract_rpc_result") as mock_extract:
                            # Setup mocks
                            mock_client = MagicMock()
                            mock_client.post.return_value = MagicMock(text="", status_code=200)
                            mock_get_client.return_value = mock_client
                            mock_extract.return_value = {}  # Non-None means success

                            mixin = NotebookMixin(cookies={"test": "cookie"}, csrf_token="test")
                            result = mixin.delete_notebook("notebook_id_123")

                            # Verify correct RPC ID was used
                            mock_build_body.assert_called_once()
                            assert (
                                mock_build_body.call_args[0][0] == "WWINqb"
                            )  # RPC_DELETE_NOTEBOOK
                            assert result is True  # Should return True on success


def test_get_notebook_passes_timeout_to_rpc():
    from notebooklm_tools.core.notebooks import NotebookMixin

    with patch.object(NotebookMixin, "_call_rpc", return_value=[]) as mock_rpc:
        mixin = NotebookMixin(cookies={"test": "cookie"}, csrf_token="test")
        mixin.get_notebook("nb-123", timeout=12.5)

    mock_rpc.assert_called_once_with(
        mixin.RPC_GET_NOTEBOOK,
        ["nb-123", None, [2], None, 0],
        "/notebook/nb-123",
        timeout=12.5,
    )
