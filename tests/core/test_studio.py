#!/usr/bin/env python3
"""Tests for StudioMixin."""

from unittest.mock import MagicMock

import pytest

from notebooklm_tools.core.base import BaseClient
from notebooklm_tools.core.studio import StudioMixin


class TestStudioMixinImport:
    """Test that StudioMixin can be imported correctly."""

    def test_studio_mixin_import(self):
        """Test that StudioMixin can be imported."""
        assert StudioMixin is not None

    def test_studio_mixin_inherits_base(self):
        """Test that StudioMixin inherits from BaseClient."""
        assert issubclass(StudioMixin, BaseClient)

    def test_studio_mixin_has_creation_methods(self):
        """Test that StudioMixin has creation methods."""
        expected_methods = [
            "create_audio_overview",
            "create_video_overview",
            "create_infographic",
            "create_slide_deck",
            "create_report",
            "create_flashcards",
            "create_quiz",
            "create_data_table",
        ]
        for method in expected_methods:
            assert hasattr(StudioMixin, method), f"Missing method: {method}"

    def test_studio_mixin_has_status_methods(self):
        """Test that StudioMixin has status methods."""
        expected_methods = [
            "poll_studio_status",
            "get_studio_status",
            "delete_studio_artifact",
            "delete_mind_map",
        ]
        for method in expected_methods:
            assert hasattr(StudioMixin, method), f"Missing method: {method}"

    def test_studio_mixin_has_mind_map_methods(self):
        """Test that StudioMixin has mind map methods."""
        expected_methods = [
            "generate_mind_map",
            "save_mind_map",
            "list_mind_maps",
        ]
        for method in expected_methods:
            assert hasattr(StudioMixin, method), f"Missing method: {method}"


class TestStudioMixinMethods:
    """Test StudioMixin method behavior."""

    def test_create_report_validates_format(self):
        """Test that create_report validates report_format parameter."""
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")

        with pytest.raises(ValueError, match="Invalid report_format"):
            mixin.create_report("notebook-id", ["source-id"], report_format="invalid")

    def test_get_studio_status_is_alias(self):
        """Test that get_studio_status is an alias for poll_studio_status."""
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")

        # Verify method exists and is callable
        assert callable(mixin.get_studio_status)
        # Method docstring should indicate it's an alias
        assert "Alias" in mixin.get_studio_status.__doc__

    def test_normalize_studio_status_treats_audio_status_2_with_media_as_completed(self):
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")

        artifact_data = [
            "art-1",
            "Audio Artifact",
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

        assert mixin._normalize_studio_status(artifact_data) == "completed"

    def test_normalize_studio_status_keeps_unverified_code_unknown(self):
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")

        artifact_data = [
            "art-2",
            "Unknown Artifact",
            mixin.STUDIO_TYPE_REPORT,
            [],
            2,
        ]

        assert mixin._normalize_studio_status(artifact_data) == "unknown"

    def test_normalize_studio_status_handles_non_list_payloads(self):
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")

        assert mixin._normalize_studio_status("unexpected-payload") == "unknown"
        assert mixin._normalize_studio_status({"status": 3}) == "unknown"
        assert mixin._normalize_studio_status(["too-short"]) == "unknown"

    def test_extract_audio_media_url_prefers_media_list_over_thumbnail_slot(self):
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")

        artifact_data = [
            "art-1",
            "Audio Artifact",
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
                [
                    ["https://example.com/audio-stream.m3u8", 2],
                    ["https://example.com/audio.m4a", 1, "audio/mp4"],
                ],
                [],
            ],
        ]

        assert mixin._extract_audio_media_url(artifact_data) == "https://example.com/audio.m4a"

    def test_extract_artifact_source_ids_reads_top_level_field_any_type(self):
        """Top-level [3] is the documented, type-agnostic source field."""
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")

        artifact_data = [
            "art-1",
            "Report Artifact",
            mixin.STUDIO_TYPE_REPORT,
            [["uuid-x"], ["uuid-y"]],  # [3] Source IDs used
            3,
            None,
        ]

        assert mixin._extract_artifact_source_ids(artifact_data, mixin.STUDIO_TYPE_REPORT) == [
            "uuid-x",
            "uuid-y",
        ]

    def test_extract_artifact_source_ids_reads_live_triple_nested_shape(self):
        """Poll responses wrap each source UUID in two single-element lists."""
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")

        artifact_data = [
            "art-1",
            "Video Artifact",
            mixin.STUDIO_TYPE_VIDEO,
            [[["uuid-x"]], [["uuid-y"]]],
            3,
            None,
        ]

        assert mixin._extract_artifact_source_ids(artifact_data, mixin.STUDIO_TYPE_VIDEO) == [
            "uuid-x",
            "uuid-y",
        ]

    def test_extract_artifact_source_ids_accepts_flat_string_entries(self):
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")

        artifact_data = [
            "art-1",
            "Audio Artifact",
            mixin.STUDIO_TYPE_AUDIO,
            ["uuid-a", "uuid-b"],  # bare strings instead of single-element lists
            2,
            None,
        ]

        assert mixin._extract_artifact_source_ids(artifact_data, mixin.STUDIO_TYPE_AUDIO) == [
            "uuid-a",
            "uuid-b",
        ]

    def test_extract_artifact_source_ids_falls_back_to_audio_options(self):
        """When the top-level field is empty, audio sources at [6][1][3] are used."""
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")

        artifact_data = [
            "art-1",
            "Audio Artifact",
            mixin.STUDIO_TYPE_AUDIO,
            [],  # empty top-level field -> forces the audio-options fallback
            2,
            None,
            [
                None,
                ["", 2, None, [["uuid-aaa"], ["uuid-bbb"]], "en", True, 1],
                "https://example.com/thumb",
                "https://example.com/thumb-dv",
                None,
                [["https://example.com/audio.m4a", 1, "audio/mp4"]],
                [],
            ],
        ]

        assert mixin._extract_artifact_source_ids(artifact_data, mixin.STUDIO_TYPE_AUDIO) == [
            "uuid-aaa",
            "uuid-bbb",
        ]

    def test_extract_artifact_source_ids_returns_empty_for_malformed_payload(self):
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")

        artifact_data = [
            "art-1",
            "Audio Artifact",
            mixin.STUDIO_TYPE_AUDIO,
            [],
            2,
            None,
        ]

        assert mixin._extract_artifact_source_ids(artifact_data, mixin.STUDIO_TYPE_AUDIO) == []

    def test_poll_studio_status_uses_normalized_status_mapping(self):
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")
        http_client = MagicMock()
        http_client.post.return_value = MagicMock(
            text="unused",
            raise_for_status=lambda: None,
        )

        mixin._get_client = MagicMock(return_value=http_client)
        mixin._build_request_body = MagicMock(return_value="body")
        mixin._build_url = MagicMock(return_value="url")
        mixin._parse_response = MagicMock(return_value=["parsed"])
        mixin._extract_rpc_result = MagicMock(
            return_value=[
                [
                    [
                        "art-1",
                        "Audio Artifact",
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
                ]
            ]
        )

        result = mixin.poll_studio_status("nb-1")

        assert result[0]["status"] == "completed"
        assert result[0]["audio_url"] == "https://example.com/audio.m4a"

    def test_poll_studio_status_identifies_mind_map_subtype(self):
        """Shared type code 4 with subtype 4 is a saved mind map, not flashcards."""
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")
        mixin._call_rpc = MagicMock(
            return_value=[
                [
                    [
                        "mind-map-1",
                        "Budget Map",
                        mixin.STUDIO_TYPE_FLASHCARDS,
                        [[["source-1"]]],
                        3,
                        None,
                        None,
                        None,
                        None,
                        ["", [4, None, None, "en", None, None, None, None, True]],
                    ]
                ]
            ]
        )

        result = mixin.poll_studio_status("nb-1")

        assert result[0]["artifact_id"] == "mind-map-1"
        assert result[0]["type"] == "mind_map"
        assert result[0]["flashcard_count"] is None

    def test_create_audio_overview_uses_normalized_status_mapping(self):
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")
        http_client = MagicMock()
        http_client.post.return_value = MagicMock(
            text="unused",
            raise_for_status=lambda: None,
        )

        mixin._get_client = MagicMock(return_value=http_client)
        mixin._build_request_body = MagicMock(return_value="body")
        mixin._build_url = MagicMock(return_value="url")
        mixin._parse_response = MagicMock(return_value=["parsed"])
        mixin._extract_rpc_result = MagicMock(
            return_value=[
                [
                    "art-1",
                    "Audio Artifact",
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
            ]
        )

        result = mixin.create_audio_overview("nb-1", ["src-1"])

        assert result["status"] == "completed"

    def test_create_audio_overview_keeps_unknown_for_unexpected_payload_shape(self):
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")
        http_client = MagicMock()
        http_client.post.return_value = MagicMock(
            text="unused",
            raise_for_status=lambda: None,
        )

        mixin._get_client = MagicMock(return_value=http_client)
        mixin._build_request_body = MagicMock(return_value="body")
        mixin._build_url = MagicMock(return_value="url")
        mixin._parse_response = MagicMock(return_value=["parsed"])
        mixin._extract_rpc_result = MagicMock(return_value=["unexpected-payload"])

        result = mixin.create_audio_overview("nb-1", ["src-1"])

        assert result["artifact_id"] is None
        assert result["status"] == "unknown"

    def test_revise_slide_deck_uses_normalized_failed_status(self):
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")
        mixin._call_rpc = MagicMock(return_value=[["art-2", "Revised Deck", 8, None, 4]])

        result = mixin.revise_slide_deck("art-1", [(0, "Tighten slide title")])

        assert result == {
            "artifact_id": "art-2",
            "title": "Revised Deck",
            "original_artifact_id": "art-1",
            "status": "failed",
        }


class TestCinematicVideoConstant:
    """Test that the Cinematic video format constant is correctly defined."""

    def test_cinematic_constant_value(self):
        """VIDEO_FORMAT_CINEMATIC should be 3."""
        from notebooklm_tools.core import constants

        assert constants.VIDEO_FORMAT_CINEMATIC == 3

    def test_cinematic_code_mapper_lookup(self):
        """CodeMapper should resolve 'cinematic' to 3 and back."""
        from notebooklm_tools.core import constants

        assert constants.VIDEO_FORMATS.get_code("cinematic") == 3
        assert constants.VIDEO_FORMATS.get_name(3) == "cinematic"

    def test_custom_style_code_mapper_lookup(self):
        """CodeMapper should resolve 'custom' to 2 and back."""
        from notebooklm_tools.core import constants

        assert constants.VIDEO_STYLES.get_code("custom") == 2
        assert constants.VIDEO_STYLES.get_name(2) == "custom"


class TestShortVideoFormat:
    """Test the Short video format (code 4), verified via live network capture."""

    def test_short_constant_value(self):
        """VIDEO_FORMAT_SHORT should be 4."""
        from notebooklm_tools.core import constants

        assert constants.VIDEO_FORMAT_SHORT == 4

    def test_short_code_mapper_lookup(self):
        """CodeMapper should resolve 'short' to 4 and back."""
        from notebooklm_tools.core import constants

        assert constants.VIDEO_FORMATS.get_code("short") == 4
        assert constants.VIDEO_FORMATS.get_name(4) == "short"

    def test_short_inner_options_omit_language_and_style_add_trailing_flag(self):
        """Short sends null language, no visual style fields, and a trailing `1` flag.

        Matches the payload captured from a live NotebookLM request on 2026-06-30:
        [sources_simple, None, focus_prompt, None, 4, None, None, 1]
        """
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")
        mixin._get_all_source_ids = MagicMock(return_value=["src-1"])
        mixin._call_rpc = MagicMock(return_value=[["art-1", "Title", 3, [], 1]])

        mixin.create_video_overview(
            "nb-1",
            source_ids=["src-1"],
            format_code=4,
            language="en",
            focus_prompt="Key topic",
        )

        params = mixin._call_rpc.call_args[0][1]
        inner_options = params[2][8][2]
        assert inner_options == [[["src-1"]], None, "Key topic", None, 4, None, None, 1]

    def test_short_result_reports_no_visual_style_and_english_language(self):
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")
        mixin._get_all_source_ids = MagicMock(return_value=["src-1"])
        mixin._call_rpc = MagicMock(return_value=[["art-1", "Title", 3, [], 1]])

        result = mixin.create_video_overview(
            "nb-1",
            source_ids=["src-1"],
            format_code=4,
            language="es",
            focus_prompt="Key topic",
        )

        assert result["format"] == "short"
        assert result["visual_style"] is None
        assert result["language"] == "en"
