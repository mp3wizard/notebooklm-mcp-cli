from unittest.mock import MagicMock

from notebooklm_tools.services.interactive_reports import REVIEW_LABEL, list_report_elements


def _client(statuses):
    seq = {k: list(v) for k, v in statuses.items()}
    report = {
        "artifact_id": "rep",
        "type": "interactive_report",
        "status": "completed",
        "parse_status": "ok",
        "source_ids": ["s"],
        "report_elements": [{"element_id": e} for e in statuses],
        "report_sections": {},
    }

    def describe(_nb, aid):
        if aid == "rep":
            return report
        status = seq[aid].pop(0) if len(seq[aid]) > 1 else seq[aid][0]
        kind = "quiz" if aid.startswith("q") else "audio"
        return {"artifact_id": aid, "type": kind, "status": status, "title": aid}

    client = MagicMock()
    client.describe_artifact.side_effect = describe
    client.get_interactive_app_data.return_value = {"quiz": [{"question": "Q1"}]}
    return client


def test_waits_until_listed_ids_finish():
    client = _client({"q1": ["queued", "queued", "completed"], "a1": ["suggested"]})
    clock = iter(range(0, 10_000, 15))
    result = list_report_elements(
        client, "nb", "rep", wait_for=["q1"], _sleep=lambda *_: None, _monotonic=lambda: next(clock)
    )
    assert result["timed_out"] is False
    assert {e["element_id"]: e["element_status"] for e in result["elements"]}["q1"] == "completed"


def test_times_out_without_error():
    client = _client({"q1": ["queued"]})
    clock = iter(range(0, 10_000, 400))
    result = list_report_elements(
        client,
        "nb",
        "rep",
        wait_for=["q1"],
        timeout=600,
        _sleep=lambda *_: None,
        _monotonic=lambda: next(clock),
    )
    assert result["timed_out"] is True


def test_unknown_wait_ids_are_missing():
    client = _client({"q1": ["completed"]})
    result = list_report_elements(client, "nb", "rep", wait_for=["ghost"], _sleep=lambda *_: None)
    assert {"element_id": "ghost", "element_status": "missing"} in result["elements"]


def test_inline_content_for_reviewable_kinds_only():
    client = _client({"q1": ["completed"], "a1": ["completed"]})
    result = list_report_elements(client, "nb", "rep", include_content=True)
    by_id = {e["element_id"]: e for e in result["elements"]}
    assert by_id["q1"]["content"] == {"questions": [{"question": "Q1"}]}
    assert by_id["a1"]["content_note"] == "not reviewable in v1"
    assert result["review_label"] == REVIEW_LABEL


def test_unreadable_content_is_reported_per_element():
    client = _client({"q1": ["completed"], "q2": ["completed"]})
    client.get_interactive_app_data.side_effect = [
        RuntimeError("parse failed"),
        {"quiz": [{"question": "Q"}]},
    ]
    result = list_report_elements(client, "nb", "rep", include_content=True)
    by_id = {e["element_id"]: e for e in result["elements"]}
    assert by_id["q1"]["content"] is None
    assert by_id["q1"]["content_note"].startswith("content unavailable")
    assert by_id["q2"]["content"] == {"questions": [{"question": "Q"}]}
