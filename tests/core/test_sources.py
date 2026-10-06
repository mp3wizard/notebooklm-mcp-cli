"""Tests for SourceMixin class."""

from unittest.mock import MagicMock, patch

import pytest


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


def _drive_pdf_metadata(mime_type="application/pdf", drive_id="drive-file-id"):
    """Metadata shape captured from a file added through the web UI Drive picker."""
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
        [drive_id, 4, mime_type, ""],
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


@pytest.mark.parametrize(
    "mime_type",
    [
        "application/pdf",
        "text/plain",
        "text/markdown",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ],
)
def test_get_notebook_sources_marks_drive_linked_type_14_files_syncable(mime_type):
    from notebooklm_tools.core.sources import SourceMixin

    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
    mixin.get_notebook = MagicMock(
        return_value=[
            [
                "Notebook",
                [[["source-1"], "drive-file", _drive_pdf_metadata(mime_type), [None, 2]]],
                "notebook-1",
            ]
        ]
    )

    source = mixin.get_notebook_sources_with_types("notebook-1")[0]

    assert source["drive_doc_id"] == "drive-file-id"
    assert source["can_sync"] is True


def test_service_drive_listing_includes_drive_picker_file():
    from notebooklm_tools.core.sources import SourceMixin
    from notebooklm_tools.services.sources import list_drive_sources

    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
    mixin.get_notebook = MagicMock(
        return_value=[
            [
                "Notebook",
                [[["source-1"], "drive-file.pdf", _drive_pdf_metadata(), [None, 2]]],
                "notebook-1",
            ]
        ]
    )
    mixin.check_source_freshness = MagicMock(return_value=True)

    result = list_drive_sources(mixin, "notebook-1")

    assert result["drive_count"] == 1
    assert result["stale_count"] == 0
    assert result["drive_sources"][0]["id"] == "source-1"
    assert result["drive_sources"][0]["drive_doc_id"] == "drive-file-id"
    assert result["drive_sources"][0]["can_sync"] is True
    mixin.check_source_freshness.assert_called_once_with("source-1")


@pytest.mark.parametrize("source_type", [1, 2])
def test_existing_drive_document_types_remain_syncable(source_type):
    from notebooklm_tools.core.sources import SourceMixin

    metadata = [
        ["drive-document-id", "version-hash"],
        None,
        None,
        None,
        source_type,
    ]
    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
    mixin.get_notebook = MagicMock(
        return_value=[["Notebook", [[["source-1"], "Drive doc", metadata]], "notebook-1"]]
    )

    source = mixin.get_notebook_sources_with_types("notebook-1")[0]

    assert source["drive_doc_id"] == "drive-document-id"
    assert source["can_sync"] is True


def test_type_14_without_drive_metadata_is_not_syncable():
    from notebooklm_tools.core.sources import SourceMixin

    metadata = _drive_pdf_metadata()[:9]
    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
    mixin.get_notebook = MagicMock(
        return_value=[["Notebook", [[["source-1"], "uploaded.pdf", metadata]], "notebook-1"]]
    )

    source = mixin.get_notebook_sources_with_types("notebook-1")[0]

    assert source["drive_doc_id"] is None
    assert source["can_sync"] is False


def test_non_drive_type_with_drive_metadata_is_not_syncable():
    from notebooklm_tools.core.sources import SourceMixin

    metadata = _drive_pdf_metadata()
    metadata[4] = 5
    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
    mixin.get_notebook = MagicMock(
        return_value=[["Notebook", [[["source-1"], "url", metadata]], "notebook-1"]]
    )

    source = mixin.get_notebook_sources_with_types("notebook-1")[0]

    assert source["drive_doc_id"] is None
    assert source["can_sync"] is False


def test_accepted_pending_drive_file_is_reconciled_by_drive_metadata():
    from notebooklm_tools.core.errors import RPCError
    from notebooklm_tools.core.sources import SourceMixin

    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
    mixin._call_rpc = MagicMock(side_effect=RPCError("accepted pending", error_code=3))
    mixin.get_notebook_sources_with_types = MagicMock(
        return_value=[{"id": "source-1", "title": "drive-file", "drive_doc_id": "drive-file-id"}]
    )

    with patch("notebooklm_tools.core.sources.time.sleep"):
        result = mixin.add_drive_source("notebook-1", "drive-file-id", "drive-file")

    assert result == {"id": "source-1", "title": "drive-file"}


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


def test_wait_for_source_ready_fails_unknown_non_media_source_immediately():
    from notebooklm_tools.core.exceptions import SourceProcessingError
    from notebooklm_tools.core.sources import SourceMixin

    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
    mixin.get_notebook_sources_with_types = MagicMock(
        return_value=[{"id": "source-1", "source_type": None, "status": 3}]
    )

    with pytest.raises(SourceProcessingError, match="source-1"):
        mixin.wait_for_source_ready(
            "notebook-1",
            "source-1",
            allow_transient_error=False,
        )

    mixin.get_notebook_sources_with_types.assert_called_once_with("notebook-1")


def test_wait_for_source_ready_allows_transient_unknown_audio_state():
    from notebooklm_tools.core.sources import SourceMixin

    ready = {"id": "source-1", "source_type": 10, "status": 2}
    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
    mixin.get_notebook_sources_with_types = MagicMock(
        side_effect=[
            [{"id": "source-1", "source_type": None, "status": 3}],
            [ready],
        ]
    )

    result = mixin.wait_for_source_ready(
        "notebook-1",
        "source-1",
        poll_interval=0,
        allow_transient_error=True,
    )

    assert result == ready


def _youtube_metadata():
    # Shape captured from a live get_source (hizoJc) response for a YouTube source.
    # The URL slot at metadata[7] is empty; the URL is at metadata[5][0].
    return [
        None,
        8553,
        [1766850041, 63757000],
        ["00000000-0000-0000-0000-000000000000", [1766850040, 782055000]],
        9,
        ["https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", "Example Channel"],
        1,
        None,
        11169,
    ]


def _web_metadata():
    return [
        None,
        1200,
        [1766850041, 63757000],
        ["00000000-0000-0000-0000-000000000000", [1766850040, 782055000]],
        5,
        None,
        1,
        ["https://example.com/article"],
    ]


def test_get_notebook_sources_returns_youtube_url_from_metadata_5():
    from notebooklm_tools.core.sources import SourceMixin

    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
    mixin.get_notebook = MagicMock(
        return_value=[
            [
                "Notebook",
                [
                    [["source-1"], "Video", _youtube_metadata(), [None, 2]],
                    [["source-2"], "Article", _web_metadata(), [None, 2]],
                ],
                "notebook-1",
            ]
        ]
    )

    sources = mixin.get_notebook_sources_with_types("notebook-1")

    assert sources[0]["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert sources[1]["url"] == "https://example.com/article"


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (_youtube_metadata(), "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        (_web_metadata(), "https://example.com/article"),
    ],
)
def test_get_source_fulltext_returns_url(metadata, expected):
    from notebooklm_tools.core.sources import SourceMixin

    mixin = SourceMixin(cookies={"test": "cookie"}, csrf_token="test")
    mixin._call_rpc = MagicMock(return_value=[[["source-1"], "Title", metadata], None, None, []])

    assert mixin.get_source_fulltext("source-1")["url"] == expected
