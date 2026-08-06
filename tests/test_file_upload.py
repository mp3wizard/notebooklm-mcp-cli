"""Tests for file upload functionality."""

import inspect
import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest

from notebooklm_tools.core import constants
from notebooklm_tools.core.exceptions import FileUploadError, FileValidationError
from notebooklm_tools.core.sources import SourceMixin
from notebooklm_tools.mcp.tools.sources import source_add


class TestFileValidation:
    """Test file validation before upload."""

    def test_nonexistent_file_raises_error(self):
        """Test that non-existent file raises FileValidationError."""
        from notebooklm_tools.core.sources import SourceMixin

        # Create a mock client with minimal setup
        client = SourceMixin.__new__(SourceMixin)
        client.cookies = {}
        client.csrf_token = "test"
        client._session_id = "test"
        client._client = None

        with pytest.raises(FileValidationError, match="File not found"):
            client.add_file("test-notebook-id", "/nonexistent/file.pdf")

    def test_empty_file_raises_error(self):
        """Test that empty file raises FileValidationError."""
        from notebooklm_tools.core.sources import SourceMixin

        client = SourceMixin.__new__(SourceMixin)
        client.cookies = {}
        client.csrf_token = "test"
        client._session_id = "test"
        client._client = None

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            temp_path = f.name

        try:
            with pytest.raises(FileValidationError, match="empty"):
                client.add_file("test-notebook-id", temp_path)
        finally:
            Path(temp_path).unlink()

    def test_directory_raises_error(self):
        """Test that directory path raises FileValidationError."""
        from notebooklm_tools.core.sources import SourceMixin

        client = SourceMixin.__new__(SourceMixin)
        client.cookies = {}
        client.csrf_token = "test"
        client._session_id = "test"
        client._client = None

        with tempfile.TemporaryDirectory() as tmpdir:  # noqa: SIM117
            with pytest.raises(FileValidationError, match="Not a regular file"):
                client.add_file("test-notebook-id", tmpdir)

    def test_unsupported_file_type_raises_error(self):
        """Test that unsupported file types raise FileValidationError."""
        from notebooklm_tools.core.sources import SourceMixin

        client = SourceMixin.__new__(SourceMixin)
        client.cookies = {}
        client.csrf_token = "test"
        client._session_id = "test"
        client._client = None

        # Create a JSON file (unsupported type)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"test": "data"}')
            temp_path = f.name

        try:
            with pytest.raises(FileValidationError, match="Unsupported file type: .json"):
                client.add_file("test-notebook-id", temp_path)
        finally:
            Path(temp_path).unlink()


class TestFileUploadProtocol:
    """Test the 3-step upload protocol."""

    def test_register_file_source_success(self):
        """Test successful file registration (step 1)."""
        from notebooklm_tools.core.sources import SourceMixin

        client = SourceMixin.__new__(SourceMixin)
        client.cookies = {"test": "cookie"}
        client.csrf_token = "test-csrf"
        client._session_id = "test-session"
        client._client = None

        # Mock the HTTP client and response
        mock_response = Mock()
        mock_response.text = ')]}\'\n100\n[["wrb.fr","o4cbdc","[[[[\\"source-id-123\\"]]]]",null,null,null,"generic"]]'
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        mock_http_client = Mock()
        mock_http_client.post = Mock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_http_client):
            source_id = client._register_file_source("notebook-123", "test.pdf")

        assert source_id == "source-id-123"
        mock_http_client.post.assert_called_once()

    def test_register_file_source_failure(self):
        """Test file registration failure."""
        from notebooklm_tools.core.sources import SourceMixin

        client = SourceMixin.__new__(SourceMixin)
        client.cookies = {"test": "cookie"}
        client.csrf_token = "test-csrf"
        client._session_id = "test-session"
        client._client = None

        # Mock response with no source ID
        mock_response = Mock()
        mock_response.text = ')]}\'\n100\n[["wrb.fr","o4cbdc","null",null,null,null,"generic"]]'
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        mock_http_client = Mock()
        mock_http_client.post = Mock(return_value=mock_response)

        with patch.object(client, "_get_client", return_value=mock_http_client):  # noqa: SIM117
            with pytest.raises(FileUploadError, match="Failed to get SOURCE_ID"):
                client._register_file_source("notebook-123", "test.pdf")

    def test_start_resumable_upload_success(self):
        """Test starting resumable upload session (step 2)."""
        from notebooklm_tools.core.sources import SourceMixin

        client = SourceMixin.__new__(SourceMixin)
        client.cookies = {"test": "cookie"}
        client.csrf_token = "test-csrf"
        client._session_id = "test-session"
        client._client = None
        client.UPLOAD_URL = "https://notebooklm.google.com/upload/_/"

        # Mock response with upload URL
        mock_response = Mock()
        mock_response.headers = {"x-goog-upload-url": "https://upload.url/session123"}
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.post = Mock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with patch.object(client, "_get_httpx_cookies", return_value=httpx.Cookies()):
                upload_url = client._start_resumable_upload(
                    "notebook-123", "test.pdf", 1024, "source-id-123"
                )

        assert upload_url == "https://upload.url/session123"

    def test_start_resumable_upload_no_url(self):
        """Test upload session start without upload URL in response."""
        from notebooklm_tools.core.sources import SourceMixin

        client = SourceMixin.__new__(SourceMixin)
        client.cookies = {"test": "cookie"}
        client.csrf_token = "test-csrf"
        client._session_id = "test-session"
        client._client = None
        client.UPLOAD_URL = "https://notebooklm.google.com/upload/_/"

        # Mock response without upload URL
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.post = Mock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with patch.object(client, "_get_httpx_cookies", return_value=httpx.Cookies()):  # noqa: SIM117
                with pytest.raises(FileUploadError, match="Failed to get upload URL"):
                    client._start_resumable_upload(
                        "notebook-123", "test.pdf", 1024, "source-id-123"
                    )

    def test_upload_file_streaming_success(self):
        """Test streaming file upload (step 3)."""
        from notebooklm_tools.core.sources import SourceMixin

        client = SourceMixin.__new__(SourceMixin)
        client.cookies = {"test": "cookie"}
        client.csrf_token = "test-csrf"
        client._session_id = "test-session"
        client._client = None

        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content for upload")
            temp_path = Path(f.name)

        try:
            # Mock successful upload
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()

            with patch("httpx.Client") as mock_client_class:
                mock_client = MagicMock()
                mock_client.__enter__ = Mock(return_value=mock_client)
                mock_client.__exit__ = Mock(return_value=False)
                mock_client.post = Mock(return_value=mock_response)
                mock_client_class.return_value = mock_client

                with patch.object(client, "_get_httpx_cookies", return_value=httpx.Cookies()):
                    client._upload_file_streaming("https://upload.url/session123", temp_path)

            # Verify post was called
            mock_client.post.assert_called_once()
        finally:
            temp_path.unlink()


class TestAddFileIntegration:
    """Test the full add_file method integration."""

    def test_add_file_orchestrates_three_steps(self):
        """Test that add_file correctly orchestrates all three steps."""
        from notebooklm_tools.core.sources import SourceMixin

        client = SourceMixin.__new__(SourceMixin)
        client.cookies = {"test": "cookie"}
        client.csrf_token = "test-csrf"
        client._session_id = "test-session"
        client._client = None

        # Create a test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content")
            temp_path = Path(f.name)

        try:
            # Mock all three steps
            with (
                patch.object(
                    client, "_register_file_source", return_value="source-id-123"
                ) as mock_register,
                patch.object(
                    client, "_start_resumable_upload", return_value="https://upload.url/session"
                ) as mock_start,
                patch.object(client, "_upload_file_streaming") as mock_upload,
            ):
                result = client.add_file("notebook-123", temp_path)

            # Verify all three steps were called
            mock_register.assert_called_once_with("notebook-123", temp_path.name)
            mock_start.assert_called_once()
            mock_upload.assert_called_once_with("https://upload.url/session", temp_path.resolve())

            # Verify result
            assert result["id"] == "source-id-123"
            assert result["title"] == temp_path.name
        finally:
            temp_path.unlink()

    def test_add_file_accepts_epub(self):
        """Test that EPUB files pass validation and use the upload protocol."""
        from notebooklm_tools.core.sources import SourceMixin

        client = SourceMixin.__new__(SourceMixin)
        client.cookies = {"test": "cookie"}
        client.csrf_token = "test-csrf"
        client._session_id = "test-session"
        client._client = None

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".epub", delete=False) as f:
            f.write(b"PK\x03\x04fake epub content")
            temp_path = Path(f.name)

        try:
            with (
                patch.object(
                    client, "_register_file_source", return_value="source-id-epub"
                ) as mock_register,
                patch.object(
                    client, "_start_resumable_upload", return_value="https://upload.url/session"
                ) as mock_start,
                patch.object(client, "_upload_file_streaming") as mock_upload,
            ):
                result = client.add_file("notebook-123", temp_path)

            mock_register.assert_called_once_with("notebook-123", temp_path.name)
            mock_start.assert_called_once()
            mock_upload.assert_called_once_with("https://upload.url/session", temp_path.resolve())

            assert result["id"] == "source-id-epub"
            assert result["title"] == temp_path.name
        finally:
            temp_path.unlink()

    @pytest.mark.parametrize(
        ("suffix", "allow_transient_error"),
        [(".txt", False), (".m4a", True)],
    )
    def test_add_file_only_tolerates_transient_error_for_media(self, suffix, allow_transient_error):
        from notebooklm_tools.core.sources import SourceMixin

        client = SourceMixin.__new__(SourceMixin)
        with tempfile.NamedTemporaryFile(mode="wb", suffix=suffix, delete=False) as f:
            f.write(b"test content")
            temp_path = Path(f.name)

        try:
            with (
                patch.object(client, "_register_file_source", return_value="source-id"),
                patch.object(client, "_start_resumable_upload", return_value="upload-url"),
                patch.object(client, "_upload_file_streaming"),
                patch.object(
                    client,
                    "wait_for_source_ready",
                    return_value={"id": "source-id", "title": temp_path.name},
                ) as mock_wait,
            ):
                client.add_file("notebook-1", temp_path, wait=True)

            mock_wait.assert_called_once_with(
                "notebook-1",
                "source-id",
                120.0,
                allow_transient_error=allow_transient_error,
            )
        finally:
            temp_path.unlink()


@pytest.mark.e2e
class TestFileUploadE2E:
    """E2E tests for file upload - requires NOTEBOOKLM_E2E=1."""

    def test_upload_text_file(self, temp_notebook):
        """Test uploading a text file (requires real authentication)."""
        from notebooklm_tools.core.auth import load_cached_tokens
        from notebooklm_tools.core.client import NotebookLMClient

        # Load real auth
        tokens = load_cached_tokens()
        if not tokens:
            pytest.skip("No authentication tokens available")

        client = NotebookLMClient(
            cookies=tokens.cookies, csrf_token=tokens.csrf_token, session_id=tokens.session_id
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content for NotebookLM upload.")
            temp_path = f.name

        try:
            result = client.add_file(temp_notebook.id, temp_path)
            assert result["id"] is not None
            assert result["title"].endswith(".txt")
        finally:
            Path(temp_path).unlink()


@pytest.fixture
def temp_notebook():
    """Create a temporary notebook for E2E tests."""
    from notebooklm_tools.core.auth import load_cached_tokens
    from notebooklm_tools.core.client import NotebookLMClient
    from notebooklm_tools.core.errors import ClientAuthenticationError

    # Load real auth
    tokens = load_cached_tokens()
    if not tokens:
        pytest.skip("No authentication tokens available")

    client = NotebookLMClient(
        cookies=tokens.cookies, csrf_token=tokens.csrf_token, session_id=tokens.session_id
    )
    try:
        notebook = client.create_notebook(title="Test Upload Notebook")
    except ClientAuthenticationError as exc:
        pytest.skip(f"Authentication tokens are expired or invalid: {exc}")

    yield notebook

    # Cleanup
    try:  # noqa: SIM105
        client.delete_notebook(notebook.id)
    except Exception:
        pass  # Ignore cleanup errors


# Gate F1: official file-extension contract alignment
EXPECTED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".txt",
        ".md",
        ".docx",
        ".csv",
        ".pptx",
        ".epub",
        ".avif",
        ".bmp",
        ".gif",
        ".heic",
        ".heif",
        ".ico",
        ".jp2",
        ".jpe",
        ".jpeg",
        ".jpg",
        ".png",
        ".tif",
        ".tiff",
        ".webp",
        ".3g2",
        ".3gp",
        ".aac",
        ".aif",
        ".aifc",
        ".aiff",
        ".amr",
        ".au",
        ".avi",
        ".cda",
        ".m4a",
        ".mid",
        ".mp3",
        ".mp4",
        ".mpeg",
        ".ogg",
        ".opus",
        ".ra",
        ".ram",
        ".snd",
        ".wav",
        ".wma",
    }
)
EXPECTED_MEDIA_EXTENSIONS = frozenset(
    {
        ".3g2",
        ".3gp",
        ".aac",
        ".aif",
        ".aifc",
        ".aiff",
        ".amr",
        ".au",
        ".avi",
        ".cda",
        ".m4a",
        ".mid",
        ".mp3",
        ".mp4",
        ".mpeg",
        ".ogg",
        ".opus",
        ".ra",
        ".ram",
        ".snd",
        ".wav",
        ".wma",
    }
)
CONTRACT_PATTERN = re.compile(r"OFFICIAL_FILE_EXTENSIONS:\s*([^\n]+)")


def _client() -> SourceMixin:
    return SourceMixin.__new__(SourceMixin)


def _parse_contract(text: str) -> frozenset[str]:
    match = CONTRACT_PATTERN.search(text)
    assert match, "official extension contract marker is missing"
    return frozenset(item.strip() for item in match.group(1).split(","))


def test_official_registry_is_exact_and_normalized() -> None:
    assert len(EXPECTED_EXTENSIONS) == 43
    assert constants.SUPPORTED_FILE_EXTENSIONS == EXPECTED_EXTENSIONS
    assert all(item.startswith(".") and item == item.lower() for item in EXPECTED_EXTENSIONS)
    assert constants.TRANSIENT_MEDIA_FILE_EXTENSIONS == EXPECTED_MEDIA_EXTENSIONS
    assert constants.TRANSIENT_MEDIA_FILE_EXTENSIONS < constants.SUPPORTED_FILE_EXTENSIONS


@pytest.mark.parametrize("extension", sorted(EXPECTED_EXTENSIONS))
def test_all_official_extensions_pass_local_gate(tmp_path: Path, extension: str) -> None:
    path = tmp_path / f"evidence{extension}"
    path.write_bytes(b"gate-f1")
    client = _client()
    with (
        patch.object(client, "_register_file_source", return_value="source-id"),
        patch.object(client, "_start_resumable_upload", return_value="upload-url"),
        patch.object(client, "_upload_file_streaming"),
    ):
        result = client.add_file("notebook-id", path)
    assert result == {"id": "source-id", "title": path.name}


@pytest.mark.parametrize("filename", ["slides.PPTX", "photo.HeIc", "clip.3GP", "audio.WmA"])
def test_extension_gate_is_case_insensitive(tmp_path: Path, filename: str) -> None:
    path = tmp_path / filename
    path.write_bytes(b"gate-f1")
    client = _client()
    with (
        patch.object(client, "_register_file_source", return_value="source-id"),
        patch.object(client, "_start_resumable_upload", return_value="upload-url"),
        patch.object(client, "_upload_file_streaming"),
    ):
        result = client.add_file("notebook-id", path)
    assert result["id"] == "source-id"


@pytest.mark.parametrize("filename", ["payload.json", "payload.exe", "extensionless"])
def test_unlisted_and_extensionless_files_remain_rejected(tmp_path: Path, filename: str) -> None:
    path = tmp_path / filename
    path.write_bytes(b"gate-f1")
    with pytest.raises(FileValidationError, match="Unsupported file type"):
        _client().add_file("notebook-id", path)


@pytest.mark.parametrize(
    ("extension", "expected"),
    [(".txt", False), (".pptx", False), (".3gp", True), (".ram", True), (".wma", True)],
)
def test_wait_processing_classification_uses_media_subset(
    tmp_path: Path, extension: str, expected: bool
) -> None:
    path = tmp_path / f"evidence{extension}"
    path.write_bytes(b"gate-f1")
    client = _client()
    with (
        patch.object(client, "_register_file_source", return_value="source-id"),
        patch.object(client, "_start_resumable_upload", return_value="upload-url"),
        patch.object(client, "_upload_file_streaming"),
        patch.object(client, "wait_for_source_ready", return_value={"id": "source-id"}) as wait,
    ):
        client.add_file("notebook-id", path, wait=True)
    wait.assert_called_once_with("notebook-id", "source-id", 120.0, allow_transient_error=expected)


def test_mcp_schema_docstring_matches_registry() -> None:
    assert _parse_contract(inspect.unwrap(source_add).__doc__ or "") == EXPECTED_EXTENSIONS


@pytest.mark.parametrize(
    "relative_path",
    [
        "src/notebooklm_tools/data/SKILL.md",
        "src/notebooklm_tools/cli/ai_docs.py",
        "docs/FILE_UPLOAD_IMPLEMENTATION.md",
    ],
)
def test_bundled_documentation_matches_registry(relative_path: str) -> None:
    repository = Path(__file__).resolve().parents[1]
    assert (
        _parse_contract((repository / relative_path).read_text(encoding="utf-8"))
        == EXPECTED_EXTENSIONS
    )
