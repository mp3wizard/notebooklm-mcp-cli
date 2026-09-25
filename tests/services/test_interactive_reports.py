"""Tests for interactive report support (type 11).

Covers payload construction, artifact parsing, markdown rendering, element
generation, the service layer, and the download path. Fixtures mirror the
shapes observed in live NotebookLM traffic (R7cb6c create, v9rmvd artifact
reads, rc3d8d field updates, Rytqqe generation kickoff).
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from notebooklm_tools.core import constants
from notebooklm_tools.core.download import DownloadMixin
from notebooklm_tools.core.studio import (
    StudioMixin,
    build_artifact_generation_payloads,
    classify_artifact_kind,
    extract_interactive_report_elements,
    extract_report_sections,
    interactive_report_document,
    interactive_report_options,
    interactive_report_parse_status,
    render_interactive_report_markdown,
)
from notebooklm_tools.services.errors import NotFoundError, ServiceError, ValidationError
from notebooklm_tools.services.interactive_reports import (
    describe_element_settings,
    resolve_element_settings,
)
from notebooklm_tools.services.studio import (
    create_artifact,
    generate_report_element,
    get_report,
    list_report_elements,
)

# ---------- Synthetic payload builders (mirror live shapes) ----------


def _heading(title):
    return [None, None, [[[None, None, [title]]], [None, 5]]]


def _para(start, end, text, attrs=None):
    span = [start, end, [text, attrs]] if attrs is not None else [start, end, [text]]
    return [start, end, [[span]]]


def _bullet(start, end, text, index=1):
    span = [start, end, [text]]
    meta = [None, None, 0, {"101": "\u2022", "102": 1, "103": index, "104": index - 1}]
    return [start, end, [[span], [None, 1], None, meta]]


def _embed(element_id, flag=1):
    return [None] * 12 + [[element_id, flag]]


def completed_report_artifact(element_ids=("el-1", "el-2"), prompt="Do the thing", language="en"):
    blocks = [
        _heading("Introduction"),
        _para(0, 12, "Hello world."),
        _bullet(12, 22, "First item"),
        _bullet(22, 33, "Second item", index=2),
        _para(33, 60, "Bold: ", attrs=[True]),
    ]
    blocks.extend(_embed(e) for e in element_ids)

    artifact = [None] * 35
    artifact[0] = "report-1"
    artifact[1] = "My Report"
    artifact[2] = constants.STUDIO_TYPE_INTERACTIVE_REPORT
    artifact[3] = []
    artifact[4] = 3
    artifact[34] = [[[blocks]], [prompt, language, True]]
    return artifact


def suggested_element(element_id="el-1", subtype=4, title="Integration Architecture"):
    # Live suggested elements are 36 long with [title, card description] at 35.
    artifact = [None] * 36
    artifact[0] = element_id
    artifact[1] = title
    artifact[2] = constants.STUDIO_TYPE_FLASHCARDS
    artifact[3] = [[["src-1"]]]
    artifact[4] = 5
    artifact[9] = ["", [subtype, None, None, "en", None, None, None, None, True]]
    artifact[35] = [title, "A visual mapping."]
    return artifact


def suggested_typed_element(type_code, element_id="el-x", title="Typed"):
    artifact = [None] * 36
    artifact[0] = element_id
    artifact[1] = title
    artifact[2] = type_code
    artifact[3] = [[["src-1"]]]
    artifact[4] = 5
    artifact[35] = [title, "desc"]
    return artifact


# ---------- Parsing and rendering ----------


class TestInteractiveReportParsing:
    def test_options_extracted_from_generated_artifact(self):
        options = interactive_report_options(completed_report_artifact())
        assert options["prompt"] == "Do the thing"
        assert options["language"] == "en"
        assert options["generated"] is True

    def test_options_from_pre_generation_artifact(self):
        artifact = [None] * 35
        artifact[34] = [None, ["Write a lesson", "fr"]]
        options = interactive_report_options(artifact)
        assert options["prompt"] == "Write a lesson"
        assert options["language"] == "fr"
        assert options["generated"] is None

    def test_document_and_elements(self):
        artifact = completed_report_artifact(element_ids=("el-a", "el-b", "el-c"))
        blocks = interactive_report_document(artifact)
        assert blocks is not None
        assert len(blocks) == 8  # 5 content blocks + 3 embeds

        elements = extract_interactive_report_elements(artifact)
        assert [e["element_id"] for e in elements] == ["el-a", "el-b", "el-c"]
        assert all(e["flag"] == 1 for e in elements)

    def test_document_missing_returns_none(self):
        artifact = [None] * 35
        artifact[34] = [None, ["prompt", "en"]]
        assert interactive_report_document(artifact) is None
        assert extract_interactive_report_elements(artifact) == []

    def test_classify_artifact_kind(self):
        assert classify_artifact_kind(completed_report_artifact()) == "interactive_report"
        assert classify_artifact_kind(suggested_element(subtype=4)) == "mind_map"
        assert classify_artifact_kind(suggested_element(subtype=2)) == "quiz"
        assert classify_artifact_kind(suggested_element(subtype=1)) == "flashcards"


class TestMarkdownRenderer:
    def test_renders_headings_paragraphs_bullets_and_embeds(self):
        artifact = completed_report_artifact(element_ids=("el-a",))
        markdown = render_interactive_report_markdown(artifact)
        assert markdown is not None
        assert "## Introduction" in markdown
        assert "Hello world." in markdown
        assert "- First item" in markdown
        assert "- Second item" in markdown
        assert "**Bold: **" in markdown
        assert "[Embedded element: el-a]" in markdown

    def test_returns_none_without_document(self):
        assert render_interactive_report_markdown([None] * 35) is None


# ---------- Core creation payload ----------


class TestCreateInteractiveReportPayload:
    def _mixin(self):
        return StudioMixin(cookies={"test": "cookie"}, csrf_token="test")

    def test_payload_matches_observed_shape(self):
        mixin = self._mixin()
        create_response = completed_report_artifact()
        create_response[4] = 2
        mixin._call_rpc = MagicMock(return_value=[create_response])

        result = mixin.create_interactive_report(
            "nb-1",
            source_ids=["s1", "s2"],
            template="learning_overview",
            custom_prompt="Write a lesson",
            language="en",
        )

        assert result is not None
        assert result["artifact_id"] == "report-1"
        assert result["type"] == "interactive_report"
        assert result["status"] == "queued"

        args = mixin._call_rpc.call_args
        assert args[0][0] == mixin.RPC_CREATE_STUDIO
        config, notebook_id, content = args[0][1]
        assert notebook_id == "nb-1"
        assert config == [
            2,
            None,
            None,
            [1, None, None, None, None, None, None, None, None, None, [1]],
            [[1, 4, 8, 10, 14, 2, 3, 6]],
        ]
        assert len(content) == 35
        assert content[2] == constants.STUDIO_TYPE_INTERACTIVE_REPORT
        assert content[3] == [[["s1"]], [["s2"]]]
        assert content[34] == [None, ["Write a lesson", "en"]]
        # Everything between sources and options is null padding.
        assert all(item is None for item in content[4:34])

    def test_invalid_template_raises(self):
        mixin = self._mixin()
        mixin._call_rpc = MagicMock(return_value=None)
        with pytest.raises(ValueError):
            mixin.create_interactive_report("nb-1", source_ids=["s1"], template="nope")

    def test_no_sources_raises(self):
        mixin = self._mixin()
        with pytest.raises(ValueError):
            mixin.create_interactive_report("nb-1", source_ids=[])


# ---------- Start artifact generation ----------


class TestStartArtifactGeneration:
    def _mixin_with_element(self, element=None):
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")
        element = element or suggested_element()
        mixin.get_artifact = MagicMock(return_value=element)

        calls = []

        def fake_rpc(rpc_id, params, path=None, **kwargs):
            calls.append((rpc_id, params))
            if rpc_id == "rc3d8d":
                return element
            return [[element[0], element[1], element[2], [], 2]]

        mixin._call_rpc = fake_rpc
        return mixin, calls

    def test_two_step_flow_payloads(self):
        mixin, calls = self._mixin_with_element()

        result = mixin.start_artifact_generation(
            "nb-1",
            "el-1",
            steering_prompt="New prompt",
            language="en",
        )

        assert [c[0] for c in calls] == ["rc3d8d", "Rytqqe"]

        _, update_params = calls[0]
        sparse, mask, _, config = update_params
        assert sparse[0] == "el-1"
        assert sparse[3] == [[["src-1"]]]
        assert sparse[9] == [None, [4, None, "New prompt", "en"]]
        assert mask == [
            [
                "app.generation_options.free_text_steering_prompt",
                "app.generation_options.language_code",
                "sources",
            ]
        ]
        assert config[4] == [[1, 4, 8, 10, 14, 2, 3, 6, 7]]

        # Captured from the report page: the element id is a plain string (not
        # wrapped in a list) and every kind shares one kickoff config.
        _, kickoff_params = calls[1]
        assert kickoff_params == [
            [2, None, None, [1] + [None] * 9 + [[1]], [[1, 4, 8, 10, 14, 2, 3, 6]]],
            "el-1",
        ]

        assert result is not None
        assert result["artifact_id"] == "el-1"
        assert result["status"] == "queued"

    @pytest.mark.parametrize(
        "type_code",
        [
            constants.STUDIO_TYPE_INFOGRAPHIC,
            constants.STUDIO_TYPE_AUDIO,
            constants.STUDIO_TYPE_VIDEO,
        ],
    )
    def test_generating_element_reports_queued(self, type_code):
        # Observed live: these elements sit at code 2 while generating.
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")
        element = suggested_typed_element(type_code)
        element[4] = 2
        assert mixin._normalize_studio_status(element) == "queued"

    def test_no_sources_refuses_without_notebook_fallback(self):
        element = suggested_element()
        element[3] = None  # suggested type-4 elements are observed without sources
        mixin, calls = self._mixin_with_element(element)
        mixin._get_all_source_ids = MagicMock(return_value=["every", "notebook", "source"])
        with pytest.raises(ValueError):
            mixin.start_artifact_generation("nb-1", "el-1")
        mixin._get_all_source_ids.assert_not_called()
        assert calls == []

    def test_explicit_source_ids_are_used(self):
        element = suggested_element()
        element[3] = None
        mixin, calls = self._mixin_with_element(element)
        mixin.start_artifact_generation("nb-1", "el-1", source_ids=["rep-src"])
        assert calls[0][1][0][3] == [[["rep-src"]]]

    def test_report_shaped_source_entries_parse(self):
        # Interactive reports store sources as [[["id"], null, 5], ...].
        assert StudioMixin._coerce_source_ids([[["a"], None, 5], [["b"], None, 5]]) == ["a", "b"]
        assert StudioMixin._coerce_source_ids([[["a"]], "b"]) == ["a", "b"]

    def test_missing_artifact_raises(self):
        mixin = StudioMixin(cookies={"test": "cookie"}, csrf_token="test")
        mixin.get_artifact = MagicMock(return_value=None)
        with pytest.raises(ValueError):
            mixin.start_artifact_generation("nb-1", "missing", steering_prompt="x")

    def test_kickoff_is_sent_without_server_retry(self):
        mixin, calls = self._mixin_with_element()
        seen = {}

        def fake_rpc(rpc_id, params, path=None, **kwargs):
            seen[rpc_id] = kwargs
            calls.append((rpc_id, params))
            return [["el-1", "T", 4, [], 2]] if rpc_id == "Rytqqe" else None

        mixin._call_rpc = fake_rpc
        mixin.start_artifact_generation("nb-1", "el-1", source_ids=["s"])
        assert seen["Rytqqe"] == {"retry_server_errors": False}

    def test_lost_kickoff_response_is_unknown(self):
        import httpx

        from notebooklm_tools.core.errors import KickoffOutcomeUnknownError

        mixin, _ = self._mixin_with_element()

        def fake_rpc(rpc_id, params, path=None, **kwargs):
            if rpc_id == "Rytqqe":
                raise httpx.ReadTimeout("lost")
            return None

        mixin._call_rpc = fake_rpc
        with pytest.raises(KickoffOutcomeUnknownError):
            mixin.start_artifact_generation("nb-1", "el-1", source_ids=["s"])

    def test_malformed_kickoff_response_is_unknown(self):
        from notebooklm_tools.core.errors import KickoffOutcomeUnknownError

        mixin, _ = self._mixin_with_element()
        mixin._call_rpc = lambda rpc_id, params, path=None, **kw: None
        with pytest.raises(KickoffOutcomeUnknownError):
            mixin.start_artifact_generation("nb-1", "el-1", source_ids=["s"])

    def test_connect_timeout_is_a_definite_failure_not_unknown(self):
        import httpx

        mixin, _ = self._mixin_with_element()

        def fake_rpc(rpc_id, params, path=None, **kwargs):
            if rpc_id == "Rytqqe":
                raise httpx.ConnectTimeout("never connected")
            return None

        mixin._call_rpc = fake_rpc
        with pytest.raises(httpx.ConnectTimeout):
            mixin.start_artifact_generation("nb-1", "el-1", source_ids=["s"])


class TestPerKindGenerationPayloads:
    """Payload shapes captured live per element kind (rc3d8d + Rytqqe)."""

    sources = [[["src-1"]]]

    def test_quiz_payload(self):
        element = suggested_element(subtype=2)
        update, mask = build_artifact_generation_payloads(element, self.sources, "Quiz me", "en")
        assert update[9] == [None, [2, None, "Quiz me", "en", None, None, None, [2, 2]]]
        assert mask == [
            [
                "app.generation_options.free_text_steering_prompt",
                "app.generation_options.language_code",
                "app.generation_options.quiz_generation_options.question_quantity",
                "app.generation_options.quiz_generation_options.quiz_difficulty",
                "sources",
            ]
        ]

    def test_flashcards_payload(self):
        element = suggested_element(subtype=1)
        update, mask = build_artifact_generation_payloads(element, self.sources, "Cards", "en")
        assert update[9] == [None, [1, None, "Cards", "en", None, None, [1, 2]]]
        assert "app.generation_options.flashcards_generation_options.card_quantity" in mask[0]

    def test_infographic_payload(self):
        element = suggested_typed_element(constants.STUDIO_TYPE_INFOGRAPHIC)
        update, mask = build_artifact_generation_payloads(element, self.sources, "Diagram", "en")
        assert len(update) == 15
        assert update[14] == [["Diagram", "en", None, 1, 2, 1]]
        assert mask == [
            [
                "infographic.generation_options.user_steering_prompt",
                "infographic.generation_options.language_code",
                "infographic.generation_options.aspect_ratio",
                "infographic.generation_options.information_density",
                "infographic.generation_options.style",
                "sources",
            ]
        ]

    def test_slide_deck_payload(self):
        element = suggested_typed_element(constants.STUDIO_TYPE_SLIDE_DECK)
        update, mask = build_artifact_generation_payloads(element, self.sources, "Deck", "en")
        assert len(update) == 17
        assert update[16] == [["Deck", "en", 1, 3]]
        assert mask == [
            [
                "slides.generation_options.user_steering_prompt",
                "slides.generation_options.language_code",
                "slides.generation_options.deck_type",
                "slides.generation_options.length",
                "sources",
            ]
        ]

    def test_mind_map_payload(self):
        element = suggested_element(subtype=4)
        update, mask = build_artifact_generation_payloads(element, self.sources, "Map", "en")
        assert update[9] == [None, [4, None, "Map", "en"]]
        assert mask == [
            [
                "app.generation_options.free_text_steering_prompt",
                "app.generation_options.language_code",
                "sources",
            ]
        ]

    def test_audio_payload(self):
        element = suggested_typed_element(constants.STUDIO_TYPE_AUDIO)
        update, mask = build_artifact_generation_payloads(element, self.sources, "Chat", "en")
        assert len(update) == 7
        assert update[6] == [None, ["Chat", 2, None, None, "en", None, 2]]
        assert mask == [
            [
                "audio_overview.generation_options.episode_focus",
                "audio_overview.generation_options.episode_length",
                "audio_overview.generation_options.language_code",
                "audio_overview.generation_options.show_format",
                "sources",
            ]
        ]

    def test_video_payload(self):
        element = suggested_typed_element(constants.STUDIO_TYPE_VIDEO)
        update, mask = build_artifact_generation_payloads(element, self.sources, "Film", "en")
        assert len(update) == 9
        assert update[8] == [None, None, [None, "en", "Film", None, 3, 1]]
        assert mask == [
            [
                "explainer_video.generation_options.language_code",
                "explainer_video.generation_options.video_focus",
                "explainer_video.generation_options.template_format",
                "explainer_video.generation_options.video_overview_style",
                "sources",
            ]
        ]

    def test_quiz_settings(self):
        update, _ = build_artifact_generation_payloads(
            suggested_element(subtype=2), self.sources, "Q", "en", {"amount": 3, "difficulty": 1}
        )
        assert update[9][1][7] == [3, 1]

    def test_flashcards_default_is_fewer_medium(self):
        update, _ = build_artifact_generation_payloads(
            suggested_element(subtype=1), self.sources, "F", "en"
        )
        assert update[9][1][6] == [1, 2]

    def test_infographic_settings(self):
        el = suggested_typed_element(constants.STUDIO_TYPE_INFOGRAPHIC)
        update, _ = build_artifact_generation_payloads(
            el,
            self.sources,
            "I",
            "en",
            {"orientation": 2, "detail_level": 3, "infographic_style": 10},
        )
        assert update[14] == [["I", "en", None, 2, 3, 10]]

    def test_slide_settings(self):
        el = suggested_typed_element(constants.STUDIO_TYPE_SLIDE_DECK)
        update, _ = build_artifact_generation_payloads(
            el, self.sources, "S", "en", {"slide_format": 2}
        )
        assert update[16] == [["S", "en", 2, 3]]

    def test_audio_uses_customize_mask(self):
        el = suggested_typed_element(constants.STUDIO_TYPE_AUDIO)
        update, mask = build_artifact_generation_payloads(
            el, self.sources, "A", "fr", {"audio_format": 4}
        )
        assert update[6] == [None, ["A", 2, None, None, "fr", None, 4]]
        assert "audio_overview.generation_options.episode_length" in mask[0]

    def test_slide_short_length_uses_captured_code(self):
        # Captured 2026-09-24: report slide "Short" sends length 2 (not 1).
        el = suggested_typed_element(constants.STUDIO_TYPE_SLIDE_DECK)
        update, _ = build_artifact_generation_payloads(
            el, self.sources, "S", "en", {"slide_length": 2}
        )
        assert update[16] == [["S", "en", 1, 2]]

    def test_short_video_omits_style_like_the_page(self):
        # Captured 2026-09-24: Short sends format 4 with the plain mask, no style field.
        el = suggested_typed_element(constants.STUDIO_TYPE_VIDEO)
        update, mask = build_artifact_generation_payloads(
            el, self.sources, "V", "en", {"video_format": 4}
        )
        assert update[8] == [None, None, [None, "en", "V", None, 4]]
        assert "explainer_video.generation_options.video_overview_style" not in mask[0]
        assert "explainer_video.generation_options.template_format" in mask[0]

    def test_video_uses_customize_mask(self):
        el = suggested_typed_element(constants.STUDIO_TYPE_VIDEO)
        update, mask = build_artifact_generation_payloads(
            el, self.sources, "V", "en", {"video_format": 1}
        )
        assert update[8] == [None, None, [None, "en", "V", None, 1, 1]]
        assert "explainer_video.generation_options.video_overview_style" in mask[0]

    def test_unknown_kind_falls_back_to_generic_mask(self):
        element = suggested_typed_element(99)
        update, mask = build_artifact_generation_payloads(element, self.sources, "x", "en")
        assert mask == [
            [
                "app.generation_options.free_text_steering_prompt",
                "app.generation_options.language_code",
                "sources",
            ]
        ]


# ---------- Service layer ----------


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_notebook_sources_with_types.return_value = [{"id": "src-1"}]
    client.create_interactive_report.return_value = {
        "artifact_id": "art-11",
        "status": "queued",
    }
    client.create_report.return_value = {"artifact_id": "art-5", "status": "in_progress"}
    return client


class TestServiceCreateDispatch:
    def test_interactive_format_dispatches_to_interactive_create(self, mock_client):
        result = create_artifact(
            mock_client,
            "nb-1",
            "report",
            report_format="Interactive",
            report_template="learning_overview",
            custom_prompt="Write a lesson",
        )

        mock_client.create_interactive_report.assert_called_once_with(
            "nb-1",
            source_ids=["src-1"],
            template="learning_overview",
            custom_prompt="Write a lesson",
            language="en",
        )
        mock_client.create_report.assert_not_called()
        assert result["artifact_id"] == "art-11"

    def test_interactive_report_alias(self, mock_client):
        create_artifact(mock_client, "nb-1", "interactive_report", custom_prompt="x")
        mock_client.create_interactive_report.assert_called_once()
        mock_client.create_report.assert_not_called()

    def test_classic_format_still_uses_classic_create(self, mock_client):
        create_artifact(mock_client, "nb-1", "report", report_format="Study Guide")
        mock_client.create_report.assert_called_once()
        mock_client.create_interactive_report.assert_not_called()

    def test_invalid_format_raises(self, mock_client):
        with pytest.raises(ValidationError):
            create_artifact(mock_client, "nb-1", "report", report_format="Nope")

    def test_invalid_template_raises(self, mock_client):
        with pytest.raises(ValidationError):
            create_artifact(
                mock_client,
                "nb-1",
                "report",
                report_format="Interactive",
                report_template="nope",
            )


class TestServiceReportReads:
    def _client(self):
        client = MagicMock()
        report_info = {
            "artifact_id": "report-1",
            "title": "My Report",
            "type": "interactive_report",
            "status": "completed",
            "source_ids": ["src-1"],
            "report_prompt": "Do the thing",
            "report_language": "en",
            "report_content": "# rendered markdown",
            "report_elements": [{"element_id": "el-1", "flag": 1, "block_index": 5}],
            "report_sections": {"el-1": {"heading": "Evolution", "text": "Cyanobacteria..."}},
            "parse_status": "ok",
        }
        element_info = {
            "artifact_id": "el-1",
            "title": "Integration Architecture",
            "type": "mind_map",
            "status": "suggested",
            "source_ids": ["src-1"],
            "steering_prompt": None,
            "description": "Recommended prompt",
        }

        def describe(_notebook_id, artifact_id):
            if artifact_id == "report-1":
                return report_info
            if artifact_id == "el-1":
                return element_info
            return None

        client.describe_artifact.side_effect = describe
        return client

    def test_get_report(self):
        report = get_report(self._client(), "nb-1", "report-1")
        assert report["markdown"] == "# rendered markdown"
        assert report["prompt"] == "Do the thing"
        assert report["elements"][0]["type"] == "mind_map"
        assert report["elements"][0]["element_status"] == "suggested"

    def test_list_report_elements(self):
        elements = list_report_elements(self._client(), "nb-1", "report-1")["elements"]
        assert len(elements) == 1
        assert elements[0]["element_id"] == "el-1"

    def test_get_report_rejects_other_types(self):
        client = MagicMock()
        client.describe_artifact.return_value = {"type": "audio", "title": "Podcast"}
        with pytest.raises(ValidationError):
            get_report(client, "nb-1", "art-1")

    def test_get_report_missing_artifact(self):
        client = MagicMock()
        client.describe_artifact.return_value = None
        with pytest.raises(NotFoundError):
            get_report(client, "nb-1", "missing")

    def test_generate_element_by_type(self):
        client = self._client()
        client.start_artifact_generation.return_value = {
            "artifact_id": "el-1",
            "title": "Integration Architecture",
            "type": "mind_map",
            "status": "queued",
        }

        result = generate_report_element(client, "nb-1", "report-1", element_type="mind_map")

        assert result["outcome"] == "started"
        assert result["element_id"] == "el-1"
        assert result["element_status"] == "queued"
        kwargs = client.start_artifact_generation.call_args.kwargs
        assert kwargs["source_ids"] == ["src-1"]
        assert kwargs["language"] == "en"
        assert kwargs["steering_prompt"] == "Recommended prompt"

    def _started_language(self, client, **kwargs):
        client.start_artifact_generation.return_value = {"artifact_id": "el-1", "status": "queued"}
        generate_report_element(client, "nb-1", "report-1", element_id="el-1", **kwargs)
        return client.start_artifact_generation.call_args.kwargs["language"]

    def _client_with_report_language(self, language):
        client = self._client()
        original = client.describe_artifact.side_effect

        def describe(nb, aid):
            info = original(nb, aid)
            return {**info, "report_language": language} if aid == "report-1" else info

        client.describe_artifact.side_effect = describe
        return client

    def test_generate_element_inherits_report_language(self):
        assert self._started_language(self._client_with_report_language("fr")) == "fr"

    def test_explicit_language_overrides_report_language(self):
        client = self._client_with_report_language("fr")
        assert self._started_language(client, language="en") == "en"

    def test_language_falls_back_to_default_when_report_has_none(self, monkeypatch):
        monkeypatch.setattr(
            "notebooklm_tools.services.interactive_reports.get_default_language", lambda: "de"
        )
        assert self._started_language(self._client_with_report_language(None)) == "de"

    def test_generate_element_refuses_report_without_sources(self):
        # Never fall back to every notebook source: refuse before any mutation.
        client = self._client()
        original = client.describe_artifact.side_effect

        def describe(nb, aid):
            info = original(nb, aid)
            if aid == "report-1":
                info = {**info, "source_ids": []}
            return info

        client.describe_artifact.side_effect = describe
        with pytest.raises(ValidationError):
            generate_report_element(client, "nb-1", "report-1", element_type="mind_map")
        client.start_artifact_generation.assert_not_called()

    def test_generate_element_requires_selector(self):
        with pytest.raises(ValidationError):
            generate_report_element(self._client(), "nb-1", "report-1")

    def test_generate_element_unknown_type(self):
        with pytest.raises(NotFoundError):
            generate_report_element(self._client(), "nb-1", "report-1", element_type="audio")

    def test_list_elements_exposes_card_description(self):
        elements = list_report_elements(self._client(), "nb-1", "report-1")["elements"]
        assert elements[0]["description"] == "Recommended prompt"

    def test_generate_element_custom_prompt_overrides_description(self):
        client = self._client()
        client.start_artifact_generation.return_value = {"artifact_id": "el-1", "status": "queued"}
        generate_report_element(
            client, "nb-1", "report-1", element_id="el-1", steering_prompt="Focus on dates"
        )
        assert client.start_artifact_generation.call_args.kwargs["steering_prompt"] == (
            "Focus on dates"
        )

    def test_generate_element_wraps_core_errors(self):
        client = self._client()
        client.start_artifact_generation.side_effect = ValueError("boom")
        with pytest.raises(ServiceError):
            generate_report_element(client, "nb-1", "report-1", element_type="mind_map")


class TestElementSettings:
    def test_short_options_are_exposed(self):
        assert describe_element_settings("slide_deck")["slide_length"] == {
            "values": ["short", "default"],
            "default": "default",
        }
        assert describe_element_settings("video")["video_format"]["values"] == [
            "explainer",
            "cinematic",
            "short",
        ]
        assert resolve_element_settings("slide_deck", {"slide_length": "short"}) == {
            "slide_length": 2
        }

    def test_schema_lists_values_and_defaults(self):
        quiz = describe_element_settings("quiz")
        assert quiz["difficulty"] == {"values": ["easy", "medium", "hard"], "default": "medium"}
        assert quiz["question_amount"]["default"] == "standard"
        assert describe_element_settings("flashcards")["card_amount"]["default"] == "fewer"
        assert describe_element_settings("mind_map") == {}

    def test_resolve_normalizes_case_and_whitespace(self):
        assert resolve_element_settings(
            "quiz", {"difficulty": " Hard ", "question_amount": "MORE"}
        ) == {
            "difficulty": 3,
            "amount": 3,
        }
        assert resolve_element_settings("infographic", {"orientation": "PORTRAIT"}) == {
            "orientation": 2
        }

    def test_resolve_rejects_setting_for_wrong_kind(self):
        with pytest.raises(ValidationError, match="orientation"):
            resolve_element_settings("quiz", {"orientation": "portrait"})

    def test_resolve_rejects_unknown_value(self):
        with pytest.raises(ValidationError, match="brief"):
            resolve_element_settings("video", {"video_format": "brief"})

    def test_resolve_rejects_unsupported_kind(self):
        with pytest.raises(ValidationError):
            resolve_element_settings("unsupported", {})


class TestRicherReads:
    def test_elements_carry_section_and_settings(self):
        elements = list_report_elements(TestServiceReportReads()._client(), "nb-1", "report-1")[
            "elements"
        ]
        assert elements[0]["section"] == {"heading": "Evolution", "text": "Cyanobacteria..."}
        assert "difficulty" not in elements[0]["settings"]  # mind map has no settings
        assert elements[0]["element_status"] == "suggested"

    def test_report_carries_parse_status(self):
        report = get_report(TestServiceReportReads()._client(), "nb-1", "report-1")
        assert report["parse_status"] == "ok"


# ---------- Download ----------


class TestDownloadInteractiveReport:
    def test_download_writes_rendered_markdown_with_title(self, tmp_path):
        mixin = DownloadMixin(cookies={"test": "cookie"}, csrf_token="test")
        artifact = completed_report_artifact()
        mixin._list_raw = MagicMock(return_value=[artifact])

        output = tmp_path / "report.md"
        path = mixin.download_report("nb-1", str(output))

        content = Path(path).read_text(encoding="utf-8")
        assert content.startswith("# My Report")
        assert "## Introduction" in content
        assert "- First item" in content

    def test_download_selects_specific_interactive_artifact(self, tmp_path):
        mixin = DownloadMixin(cookies={"test": "cookie"}, csrf_token="test")
        first = completed_report_artifact()
        first[0] = "report-1"
        second = completed_report_artifact()
        second[0] = "report-2"
        second[1] = "Second Report"
        mixin._list_raw = MagicMock(return_value=[first, second])

        output = tmp_path / "second.md"
        path = mixin.download_report("nb-1", str(output), artifact_id="report-2")

        content = Path(path).read_text(encoding="utf-8")
        assert content.startswith("# Second Report")


class TestReportStructure:
    def test_sections_map_each_element_to_its_heading(self):
        blocks = [
            _heading("Intro"),
            _para(0, 5, "Hello"),
            _embed("el-1"),
            _heading("Stage Two"),
            _para(5, 20, "Calvin cycle"),
            _bullet(20, 30, "Fixation"),
            _embed("el-2"),
        ]
        artifact = completed_report_artifact(element_ids=())
        artifact[34] = [[[blocks]], ["p", "en", True]]
        sections = extract_report_sections(artifact)
        assert sections["el-1"] == {"heading": "Intro", "text": "Hello"}
        assert sections["el-2"] == {"heading": "Stage Two", "text": "Calvin cycle\nFixation"}

    def test_element_before_any_heading_has_no_section(self):
        artifact = completed_report_artifact(element_ids=())
        artifact[34] = [[[[_embed("el-1")]]], ["p", "en", True]]
        assert extract_report_sections(artifact) == {"el-1": None}

    def test_embed_with_extra_trailing_field_is_still_detected(self):
        embed = [None] * 12 + [["el-9", 1], "new-google-field"]
        artifact = completed_report_artifact(element_ids=())
        artifact[34] = [[[[_heading("H"), embed]]], ["p", "en", True]]
        assert [e["element_id"] for e in extract_interactive_report_elements(artifact)] == ["el-9"]

    def test_parse_status(self):
        pending = completed_report_artifact()
        pending[34] = [None, ["p", "en"]]
        assert interactive_report_parse_status(pending) == "pending"

        assert interactive_report_parse_status(completed_report_artifact()) == "ok"

        empty = completed_report_artifact(element_ids=())
        assert interactive_report_parse_status(empty) == "empty"

        weird = completed_report_artifact()
        weird[34] = [{"unexpected": True}, ["p", "en", True]]
        assert interactive_report_parse_status(weird) == "unrecognized"

    def test_unknown_type4_subtype_is_unsupported(self):
        assert classify_artifact_kind(suggested_element(subtype=9)) == "unsupported"
        assert classify_artifact_kind(suggested_element(subtype=1)) == "flashcards"
