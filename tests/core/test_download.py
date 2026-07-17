#!/usr/bin/env python3
"""Tests for DownloadMixin."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from notebooklm_tools.core.base import BaseClient
from notebooklm_tools.core.download import DownloadMixin
from notebooklm_tools.core.errors import ArtifactDownloadError


class TestDownloadMixinImport:
    """Test that DownloadMixin can be imported correctly."""

    def test_download_mixin_import(self):
        """Test that DownloadMixin can be imported."""
        assert DownloadMixin is not None

    def test_download_mixin_inherits_base(self):
        """Test that DownloadMixin inherits from BaseClient."""
        assert issubclass(DownloadMixin, BaseClient)

    def test_download_mixin_has_binary_download_methods(self):
        """Test that DownloadMixin has binary download methods."""
        expected_methods = [
            "download_audio",
            "download_video",
            "download_infographic",
            "download_slide_deck",
        ]
        for method in expected_methods:
            assert hasattr(DownloadMixin, method), f"Missing method: {method}"

    def test_download_mixin_has_text_download_methods(self):
        """Test that DownloadMixin has text download methods."""
        expected_methods = [
            "download_report",
            "download_mind_map",
            "download_data_table",
        ]
        for method in expected_methods:
            assert hasattr(DownloadMixin, method), f"Missing method: {method}"

    def test_download_mixin_has_interactive_download_methods(self):
        """Test that DownloadMixin has interactive download methods."""
        expected_methods = [
            "download_quiz",
            "download_flashcards",
        ]
        for method in expected_methods:
            assert hasattr(DownloadMixin, method), f"Missing method: {method}"

    def test_download_mixin_has_helper_methods(self):
        """Test that DownloadMixin has helper methods."""
        expected_methods = [
            "_download_url",
            "_list_raw",
            "_extract_cell_text",
            "_parse_data_table",
            "_get_artifact_content",
            "_extract_app_data",
        ]
        for method in expected_methods:
            assert hasattr(DownloadMixin, method), f"Missing method: {method}"


class TestDownloadMixinMethods:
    """Test DownloadMixin method behavior."""

    def _audio_artifact(self, url: str) -> list:
        mixin = DownloadMixin(cookies={"test": "cookie"}, csrf_token="test")
        return [
            "art-1",
            "Audio",
            mixin.STUDIO_TYPE_AUDIO,
            [],
            2,
            None,
            [
                None,
                ["", 2, None, [["src-1"]], "en", True, 1],
                "https://example.com/thumb",
                "https://example.com/thumb-dv",
                None,
                [[url, 4, "audio/mp4"]],
                [],
            ],
        ]

    def _download_error(self, status_code: int, final_url: str) -> ArtifactDownloadError:
        request = httpx.Request("GET", final_url)
        response = httpx.Response(status_code, request=request)
        cause = httpx.HTTPStatusError("download failed", request=request, response=response)
        error = ArtifactDownloadError("file", details="HTTP error")
        error.__cause__ = cause
        return error

    def test_extract_cell_text_handles_none(self):
        """Test that _extract_cell_text handles None input."""
        result = DownloadMixin._extract_cell_text(None)
        assert result == ""

    def test_extract_cell_text_handles_string(self):
        """Test that _extract_cell_text handles string input."""
        result = DownloadMixin._extract_cell_text("  test value  ")
        assert result == "test value"

    def test_extract_cell_text_handles_integer(self):
        """Test that _extract_cell_text handles integer input (position marker)."""
        result = DownloadMixin._extract_cell_text(42)
        assert result == ""

    def test_extract_cell_text_handles_nested_list(self):
        """Test that _extract_cell_text handles nested list input."""
        result = DownloadMixin._extract_cell_text([1, "hello", [2, "world"]])
        assert "hello" in result
        assert "world" in result

    def test_format_quiz_markdown(self):
        """Test quiz markdown formatting."""
        questions = [
            {
                "question": "What is 2+2?",
                "answerOptions": [
                    {"text": "3", "isCorrect": False},
                    {"text": "4", "isCorrect": True},
                ],
                "hint": "Think simple",
            }
        ]
        result = DownloadMixin._format_quiz_markdown("Test Quiz", questions)
        assert "# Test Quiz" in result
        assert "## Question 1" in result
        assert "What is 2+2?" in result
        assert "[x] 4" in result
        assert "[ ] 3" in result
        assert "**Hint:** Think simple" in result

    def test_format_flashcards_markdown(self):
        """Test flashcard markdown formatting."""
        cards = [{"f": "Front text", "b": "Back text"}]
        result = DownloadMixin._format_flashcards_markdown("Test Deck", cards)
        assert "# Test Deck" in result
        assert "## Card 1" in result
        assert "**Front:** Front text" in result
        assert "**Back:** Back text" in result

    def test_is_audio_artifact_ready_accepts_verified_status_2_payload(self):
        mixin = DownloadMixin(cookies={"test": "cookie"}, csrf_token="test")
        artifact = [
            "art-1",
            "Audio",
            mixin.STUDIO_TYPE_AUDIO,
            [],
            2,
            None,
            [
                None,
                ["", 2, None, [["src-1"]], "en", True, 1],
                "https://example.com/thumb",
                "https://example.com/thumb-dv",
                None,
                [["https://example.com/audio.m4a", 1, "audio/mp4"]],
                [],
            ],
        ]

        assert mixin._is_audio_artifact_ready(artifact) is True

    @pytest.mark.asyncio
    async def test_download_audio_accepts_verified_status_2_payload(self):
        mixin = DownloadMixin(cookies={"test": "cookie"}, csrf_token="test")
        artifact = [
            "art-1",
            "Audio",
            mixin.STUDIO_TYPE_AUDIO,
            [],
            2,
            None,
            [
                None,
                ["", 2, None, [["src-1"]], "en", True, 1],
                "https://example.com/thumb",
                "https://example.com/thumb-dv",
                None,
                [["https://example.com/audio.m4a", 1, "audio/mp4"]],
                [],
            ],
        ]

        mixin._list_raw = lambda notebook_id: [artifact]
        mixin._download_url = AsyncMock(return_value="/tmp/audio.m4a")

        result = await mixin.download_audio("nb-1", "/tmp/audio.m4a")

        assert result == "/tmp/audio.m4a"
        mixin._download_url.assert_awaited_once_with(
            "https://example.com/audio.m4a",
            "/tmp/audio.m4a",
            None,
        )

    @pytest.mark.asyncio
    async def test_download_audio_retries_transient_google_media_404(self):
        mixin = DownloadMixin(cookies={"test": "cookie"}, csrf_token="test")
        first_url = "https://lh3.googleusercontent.com/notebooklm/audio=m140-dv"
        second_url = "https://lh3.googleusercontent.com/notebooklm/audio2=m140-dv"
        retryable_error = self._download_error(
            404,
            "https://lh3.googleusercontent.com/rd-notebooklm/audio=s512-m140-dv",
        )

        mixin._list_raw = Mock(
            side_effect=[
                [self._audio_artifact(first_url)],
                [self._audio_artifact(second_url)],
            ]
        )
        mixin._download_url = AsyncMock(side_effect=[retryable_error, "/tmp/audio.m4a"])
        mixin._AUDIO_DOWNLOAD_RETRY_DELAYS = (0,)

        result = await mixin.download_audio("nb-1", "/tmp/audio.m4a", artifact_id="art-1")

        assert result == "/tmp/audio.m4a"
        assert mixin._list_raw.call_count == 2
        mixin._download_url.assert_any_await(first_url, "/tmp/audio.m4a", None)
        mixin._download_url.assert_any_await(second_url, "/tmp/audio.m4a", None)

    @pytest.mark.asyncio
    async def test_download_audio_does_not_retry_unrelated_404(self):
        mixin = DownloadMixin(cookies={"test": "cookie"}, csrf_token="test")
        url = "https://lh3.googleusercontent.com/notebooklm/audio=m140-dv"
        non_retryable_error = self._download_error(
            404,
            "https://example.com/not-found",
        )

        mixin._list_raw = Mock(return_value=[self._audio_artifact(url)])
        mixin._download_url = AsyncMock(side_effect=non_retryable_error)
        mixin._AUDIO_DOWNLOAD_RETRY_DELAYS = (0,)

        with pytest.raises(ArtifactDownloadError) as exc_info:
            await mixin.download_audio("nb-1", "/tmp/audio.m4a", artifact_id="art-1")

        assert exc_info.value is non_retryable_error
        assert mixin._list_raw.call_count == 1
        mixin._download_url.assert_awaited_once_with(url, "/tmp/audio.m4a", None)

    @pytest.mark.asyncio
    async def test_download_audio_reports_propagation_after_retry_exhaustion(self):
        mixin = DownloadMixin(cookies={"test": "cookie"}, csrf_token="test")
        url = "https://lh3.googleusercontent.com/notebooklm/audio=m140-dv"
        retryable_error = self._download_error(
            404,
            "https://lh3.googleusercontent.com/rd-notebooklm/audio=s512-m140-dv",
        )

        mixin._list_raw = Mock(return_value=[self._audio_artifact(url)])
        mixin._download_url = AsyncMock(side_effect=retryable_error)
        mixin._AUDIO_DOWNLOAD_RETRY_DELAYS = (0,)

        with pytest.raises(ArtifactDownloadError) as exc_info:
            await mixin.download_audio("nb-1", "/tmp/audio.m4a", artifact_id="art-1")

        assert "still propagating" in exc_info.value.details
        assert mixin._list_raw.call_count == 2
        assert mixin._download_url.await_count == 2


class TestDownloadUrlCookies:
    """Cookie handling for cross-domain artifact downloads."""

    @pytest.mark.asyncio
    async def test_download_url_strips_osid_cookies(self, tmp_path):
        """OSID cookies must be removed before issuing the download request.

        OSID is scoped to notebooklm.google.com. If it leaks onto a download
        host such as lh3.googleusercontent.com, Google treats the request as
        an invalid session and redirects to ServiceLogin.
        """
        mixin = DownloadMixin(
            cookies=[
                {"name": "SID", "value": "sid-value", "domain": ".google.com", "path": "/"},
                {"name": "OSID", "value": "osid-value", "domain": ".google.com", "path": "/"},
                {
                    "name": "__Secure-OSID",
                    "value": "secure-osid-value",
                    "domain": ".google.com",
                    "path": "/",
                },
            ],
            csrf_token="token",
        )

        captured = {}

        class MockStreamResponse:
            headers = {
                "content-length": "4",
                "content-type": "application/octet-stream",
            }

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            def raise_for_status(self):
                return None

            async def aiter_bytes(self, chunk_size=8192):
                yield b"data"

        class MockAsyncClient:
            def __init__(self, *, cookies, headers, follow_redirects, timeout):
                captured["cookies"] = cookies
                captured["headers"] = headers

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            def stream(self, method, url):
                return MockStreamResponse()

        output = tmp_path / "out.bin"

        with patch("notebooklm_tools.core.download.httpx.AsyncClient", MockAsyncClient):
            result = await mixin._download_url(
                "https://lh3.googleusercontent.com/file", str(output)
            )

        assert result == str(output)
        assert output.read_bytes() == b"data"

        cookies = captured["cookies"]
        assert cookies.get("SID", domain=".google.com") == "sid-value"
        assert cookies.get("SID", domain=".googleusercontent.com") == "sid-value"
        for domain in (".google.com", ".googleusercontent.com"):
            assert cookies.get("OSID", domain=domain) is None
            assert cookies.get("__Secure-OSID", domain=domain) is None

        headers = captured["headers"]
        assert headers.get("Sec-Fetch-Site") == "cross-site"
        assert headers.get("Referer") == f"{mixin._get_base_url()}/"


class TestDownloadMindMapNoteFiltering:
    """The notes store mixes notes and mind maps; download_mind_map must only
    consider entries whose content is real mind map JSON."""

    @staticmethod
    def _mixin_with_entries(entries):
        from unittest.mock import patch

        from notebooklm_tools.core.download import DownloadMixin

        with patch.object(DownloadMixin, "_refresh_auth_tokens"):
            mixin = DownloadMixin(cookies={"test": "cookie"}, csrf_token="test")
        patcher = patch.object(mixin, "_call_rpc", return_value=[entries])
        patcher.start()
        return mixin, patcher

    _NOTE = [
        "note-1",
        ["note-1", "Prose note content, not JSON.", [None, None, None], None, "A Note"],
        1,
    ]
    _MIND_MAP = [
        "mm-1",
        ["mm-1", '{"name": "Root", "children": []}', [None, None, None], None, "Real Map"],
        1,
    ]

    def test_unqualified_download_skips_notes(self, tmp_path):
        mixin, patcher = self._mixin_with_entries([self._NOTE, self._MIND_MAP])
        try:
            out = mixin.download_mind_map("nb-1", str(tmp_path / "mm.json"))
        finally:
            patcher.stop()
        import json as _json

        data = _json.loads((tmp_path / "mm.json").read_text(encoding="utf-8"))
        assert data == {"name": "Root", "children": []}
        assert out == str(tmp_path / "mm.json")

    def test_note_id_reports_not_found(self, tmp_path):
        import pytest as _pytest

        from notebooklm_tools.core.errors import ArtifactNotFoundError

        mixin, patcher = self._mixin_with_entries([self._NOTE, self._MIND_MAP])
        try:
            with _pytest.raises(ArtifactNotFoundError):
                mixin.download_mind_map("nb-1", str(tmp_path / "mm.json"), "note-1")
        finally:
            patcher.stop()

    def test_only_notes_reports_not_ready(self, tmp_path):
        import pytest as _pytest

        from notebooklm_tools.core.errors import ArtifactNotReadyError

        mixin, patcher = self._mixin_with_entries([self._NOTE])
        try:
            with _pytest.raises(ArtifactNotReadyError):
                mixin.download_mind_map("nb-1", str(tmp_path / "mm.json"))
        finally:
            patcher.stop()


class TestStudioMindMapDownload:
    """Mind maps stored as type-4 studio artifacts (format code 4)."""

    _MM_HTML = (
        '<div data-app-data="{&quot;name&quot;: &quot;Root&quot;, &quot;children&quot;: []}"></div>'
    )

    @staticmethod
    def _raw_type4(artifact_id, title, format_code):
        return [
            artifact_id,
            title,
            4,
            None,
            3,
            None,
            None,
            None,
            None,
            ["", [format_code, None, None, "en", None, None, None, None, True]],
        ]

    @staticmethod
    def _mixin():
        from unittest.mock import patch

        from notebooklm_tools.core.download import DownloadMixin

        with patch.object(DownloadMixin, "_refresh_auth_tokens"):
            return DownloadMixin(cookies={"test": "cookie"}, csrf_token="test")

    def test_download_mind_map_falls_back_to_studio_artifact(self, tmp_path):
        import json as _json
        from unittest.mock import patch

        mixin = self._mixin()
        raw = self._raw_type4("mm-9", "Studio Map", 4)
        with (
            patch.object(mixin, "_call_rpc", return_value=[[]]),  # notes store empty
            patch.object(mixin, "_list_raw", return_value=[raw]),
            patch.object(mixin, "_get_artifact_content", return_value=self._MM_HTML),
        ):
            out = mixin.download_mind_map("nb-1", str(tmp_path / "mm.json"), "mm-9")

        assert out == str(tmp_path / "mm.json")
        data = _json.loads((tmp_path / "mm.json").read_text(encoding="utf-8"))
        assert data == {"name": "Root", "children": []}

    def test_unqualified_download_uses_studio_when_notes_store_empty(self, tmp_path):
        import json as _json
        from unittest.mock import patch

        mixin = self._mixin()
        raw = self._raw_type4("mm-9", "Studio Map", 4)
        with (
            patch.object(mixin, "_call_rpc", return_value=[[]]),
            patch.object(mixin, "_list_raw", return_value=[raw]),
            patch.object(mixin, "_get_artifact_content", return_value=self._MM_HTML),
        ):
            out = mixin.download_mind_map("nb-1", str(tmp_path / "mm.json"))

        data = _json.loads((tmp_path / "mm.json").read_text(encoding="utf-8"))
        assert data["name"] == "Root"
        assert out == str(tmp_path / "mm.json")

    @pytest.mark.asyncio
    async def test_flashcards_download_excludes_mind_maps(self, tmp_path):
        from unittest.mock import patch

        from notebooklm_tools.core.errors import ArtifactNotReadyError

        mixin = self._mixin()
        raw = self._raw_type4("mm-9", "Studio Map", 4)
        with (
            patch.object(mixin, "_list_raw", return_value=[raw]),
            pytest.raises(ArtifactNotReadyError),
        ):
            await mixin.download_flashcards("nb-1", str(tmp_path / "cards.json"))

    @pytest.mark.asyncio
    async def test_quiz_download_still_finds_quiz(self, tmp_path):
        from unittest.mock import patch

        quiz_html = '<div data-app-data="{&quot;quiz&quot;: [{&quot;question&quot;: &quot;Q1&quot;}]}"></div>'
        mixin = self._mixin()
        raws = [
            self._raw_type4("mm-9", "Studio Map", 4),
            self._raw_type4("q-1", "The Quiz", 2),
        ]
        with (
            patch.object(mixin, "_list_raw", return_value=raws),
            patch.object(mixin, "_get_artifact_content", return_value=quiz_html) as mock_content,
        ):
            out = await mixin.download_quiz("nb-1", str(tmp_path / "quiz.json"))

        assert out == str(tmp_path / "quiz.json")
        assert mock_content.call_args[0][1] == "q-1"
