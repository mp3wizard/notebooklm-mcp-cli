"""Tests for SourceMixin class."""

from unittest.mock import MagicMock, patch


def test_source_mixin_import():
    """Test that SourceMixin can be imported."""
    from notebooklm_tools.core.sources import SourceMixin

    assert SourceMixin is not None


def test_source_mixin_inherits_base():
    """Test that SourceMixin inherits from BaseClient."""
    from notebooklm_tools.core.base import BaseClient
    from notebooklm_tools.core.sources import SourceMixin

    assert issubclass(SourceMixin, BaseClient)


def test_source_mixin_has_methods():
    """Test that SourceMixin has all expected methods."""
    from notebooklm_tools.core.sources import SourceMixin

    expected_methods = [
        "check_source_freshness",
        "sync_drive_source",
        "delete_source",
        "get_notebook_sources_with_types",
        "add_url_source",
        "add_text_source",
        "add_drive_source",
        "add_file",  # HTTP-based file upload
        "get_source_guide",
        "get_source_fulltext",
    ]

    for method_name in expected_methods:
        assert hasattr(SourceMixin, method_name), f"Missing method: {method_name}"


def test_add_url_source_uses_correct_rpc():
    """Test that add_url_source calls the correct RPC."""
    from notebooklm_tools.core.sources import SourceMixin

    with patch.object(SourceMixin, "_refresh_auth_tokens"):  # noqa: SIM117
        with patch.object(SourceMixin, "_get_client") as mock_get_client:
            mock_response = MagicMock()
            mock_response.text = ')]}\'\n[[["wrb.fr","abcdef","[[]]",null,null,null,"generic"]]]'
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with patch.object(SourceMixin, "_parse_response") as mock_parse:
                mock_parse.return_value = []
                with patch.object(SourceMixin, "_extract_rpc_result") as mock_extract:
                    mock_extract.return_value = [[[[["id123"], "Test Source"]]]]

                    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
                    mixin.add_url_source("notebook_id_123", "https://example.com")

                    mock_client.post.assert_called_once()


def test_delete_source_uses_correct_rpc():
    """Test that delete_source calls the correct RPC."""
    from notebooklm_tools.core.sources import SourceMixin

    with patch.object(SourceMixin, "_refresh_auth_tokens"):  # noqa: SIM117
        with patch.object(SourceMixin, "_get_client") as mock_get_client:
            mock_response = MagicMock()
            mock_response.text = ')]}\'\n[[["wrb.fr","abcdef","[]",null,null,null,"generic"]]]'
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with patch.object(SourceMixin, "_parse_response") as mock_parse:
                mock_parse.return_value = []
                with patch.object(SourceMixin, "_extract_rpc_result") as mock_extract:
                    mock_extract.return_value = []

                    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
                    result = mixin.delete_source("source_id_123")

                    mock_client.post.assert_called_once()
                    assert result is True


def test_get_source_guide_uses_call_rpc():
    """Test that get_source_guide uses _call_rpc."""
    from notebooklm_tools.core.sources import SourceMixin

    with patch.object(SourceMixin, "_refresh_auth_tokens"):  # noqa: SIM117
        with patch.object(SourceMixin, "_call_rpc") as mock_rpc:
            mock_rpc.return_value = []

            mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
            result = mixin.get_source_guide("source_id_123")

            mock_rpc.assert_called_once()
            assert result == {"summary": "", "keywords": []}


def _drive_pdf_metadata():
    """Metadata shape captured from a PDF added through the web UI Drive picker."""
    return [
        None,
        33405,
        [1784078147, 841477000],
        ["revision-id", [1784078147, 501725000]],
        14,
        None,
        None,
        None,
        69367,
        ["drive-file-id", 4, "application/pdf", ""],
        None,
        "document.pdf",
        None,
        None,
        [1784078154, 877897000],
        None,
        None,
        None,
        None,
        "application/pdf",
    ]


def test_get_notebook_sources_identifies_drive_picker_pdf_by_mime_type():
    from notebooklm_tools.core.sources import SourceMixin

    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
    mixin.get_notebook = MagicMock(
        return_value=[
            [
                "Notebook",
                [[["source-1"], "document.pdf", _drive_pdf_metadata(), [None, 2]]],
                "notebook-1",
            ]
        ]
    )

    sources = mixin.get_notebook_sources_with_types("notebook-1")

    assert sources[0]["source_type"] == 14
    assert sources[0]["source_type_name"] == "pdf"


def test_get_source_fulltext_identifies_drive_picker_pdf_by_mime_type():
    from notebooklm_tools.core.sources import SourceMixin

    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
    mixin._call_rpc = MagicMock(
        return_value=[
            [["source-1"], "document.pdf", _drive_pdf_metadata()],
            None,
            None,
            [],
        ]
    )

    source = mixin.get_source_fulltext("source-1")

    assert source["source_type"] == "pdf"
