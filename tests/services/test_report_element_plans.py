"""Plan parsing and validation must finish before any Google mutation."""

from unittest.mock import MagicMock

import pytest

from notebooklm_tools.services.errors import NotFoundError, ValidationError
from notebooklm_tools.services.interactive_reports import (
    parse_element_plan,
    prepare_element_plan,
)


def _client(elements=None, report_status="completed", source_ids=("src-1",), parse_status="ok"):
    elements = elements or {
        "el-quiz": {
            "type": "quiz",
            "status": "suggested",
            "title": "Quiz",
            "description": "Card Q",
        },
        "el-map": {
            "type": "mind_map",
            "status": "suggested",
            "title": "Map",
            "description": "Card M",
        },
    }
    report = {
        "artifact_id": "rep",
        "type": "interactive_report",
        "status": report_status,
        "parse_status": parse_status,
        "source_ids": list(source_ids),
        "report_language": "fr",
        "report_elements": [{"element_id": eid} for eid in elements],
        "report_sections": {},
    }

    def describe(_nb, aid):
        if aid == "rep":
            return report
        if aid in elements:
            return {"artifact_id": aid, **elements[aid]}
        return None

    client = MagicMock()
    client.describe_artifact.side_effect = describe
    return client


def test_parse_rejects_non_list():
    with pytest.raises(ValidationError):
        parse_element_plan({"element_id": "x"})


def test_parse_rejects_unknown_keys():
    with pytest.raises(ValidationError, match="unknown"):
        parse_element_plan([{"element_id": "x", "auto_approve": True}])


def test_parse_rejects_too_many_items():
    with pytest.raises(ValidationError):
        parse_element_plan([{"element_id": f"e{i}"} for i in range(21)])


def test_parse_rejects_long_prompt():
    with pytest.raises(ValidationError):
        parse_element_plan([{"element_id": "e", "steering_prompt": "x" * 4001}])


def test_prepare_resolves_language_sources_prompt_and_settings():
    plan = prepare_element_plan(
        _client(),
        "nb",
        "rep",
        [
            {
                "element_id": "el-quiz",
                "steering_prompt": "5 hard questions",
                "settings": {"difficulty": "hard"},
            },
            {"element_id": "el-map"},
        ],
    )
    assert plan.language == "fr"
    assert plan.source_ids == ["src-1"]
    assert plan.elements[0].settings == {"difficulty": 3}
    assert plan.elements[1].prompt == "Card M"  # card description default


def test_prepare_rejects_duplicates():
    with pytest.raises(ValidationError, match="more than once"):
        prepare_element_plan(
            _client(), "nb", "rep", [{"element_id": "el-quiz"}, {"element_id": "el-quiz"}]
        )


def test_prepare_rejects_non_suggested():
    client = _client(elements={"el-quiz": {"type": "quiz", "status": "completed", "title": "Q"}})
    with pytest.raises(ValidationError, match="already"):
        prepare_element_plan(client, "nb", "rep", [{"element_id": "el-quiz"}])


def test_prepare_rejects_element_not_in_report():
    with pytest.raises(NotFoundError):
        prepare_element_plan(_client(), "nb", "rep", [{"element_id": "nope"}])


def test_prepare_rejects_report_still_generating():
    with pytest.raises(ValidationError, match="not ready"):
        prepare_element_plan(
            _client(report_status="in_progress"), "nb", "rep", [{"element_id": "el-quiz"}]
        )


def test_prepare_rejects_report_without_sources():
    with pytest.raises(ValidationError, match="sources"):
        prepare_element_plan(_client(source_ids=()), "nb", "rep", [{"element_id": "el-quiz"}])


def test_prepare_rejects_bad_setting_before_anything_else():
    client = _client()
    with pytest.raises(ValidationError, match="orientation"):
        prepare_element_plan(
            client,
            "nb",
            "rep",
            [{"element_id": "el-quiz", "settings": {"orientation": "portrait"}}],
        )
    client.start_artifact_generation.assert_not_called()
