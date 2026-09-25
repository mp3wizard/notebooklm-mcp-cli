"""Single and batch element generation share one safe path."""

from unittest.mock import MagicMock

import httpx  # noqa: F401  (documents the transport errors the core wraps)

from notebooklm_tools.core.errors import (
    ClientAuthenticationError,
    KickoffOutcomeUnknownError,
    ResourceExhaustedError,
    RPCError,
)
from notebooklm_tools.services.interactive_reports import (
    generate_report_element,
    generate_report_elements,
)


# _client(...) copied from test_report_element_plans.py (three suggested elements):
def _client(elements=None):
    elements = elements or {
        "el-a": {"type": "quiz", "status": "suggested", "title": "A", "description": "da"},
        "el-b": {"type": "mind_map", "status": "suggested", "title": "B", "description": "db"},
        "el-c": {"type": "audio", "status": "suggested", "title": "C", "description": "dc"},
    }
    state = {k: dict(v) for k, v in elements.items()}
    report = {
        "artifact_id": "rep",
        "type": "interactive_report",
        "status": "completed",
        "parse_status": "ok",
        "source_ids": ["src-1"],
        "report_language": "en",
        "report_elements": [{"element_id": e} for e in elements],
        "report_sections": {},
    }

    def describe(_nb, aid):
        if aid == "rep":
            return report
        return {"artifact_id": aid, **state[aid]} if aid in state else None

    client = MagicMock()
    client.describe_artifact.side_effect = describe
    client._state = state
    return client


PLAN = [{"element_id": "el-a"}, {"element_id": "el-b"}, {"element_id": "el-c"}]


def _ok(eid):
    return {"artifact_id": eid, "title": eid, "type": "x", "status": "queued"}


def test_all_started_with_report_scope():
    client = _client()
    client.start_artifact_generation.side_effect = lambda nb, eid, **kw: _ok(eid)
    result = generate_report_elements(client, "nb", "rep", PLAN, _sleep=lambda *_: None)
    assert result["counts"] == {"started": 3, "failed": 0, "unknown": 0, "not_started": 0}
    kwargs = client.start_artifact_generation.call_args_list[0].kwargs
    assert kwargs["source_ids"] == ["src-1"] and kwargs["language"] == "en"


def test_item_rejection_continues():
    client = _client()

    def start(nb, eid, **kw):
        if eid == "el-b":
            raise RPCError("rejected", error_code=9)
        return _ok(eid)

    client.start_artifact_generation.side_effect = start
    result = generate_report_elements(client, "nb", "rep", PLAN, _sleep=lambda *_: None)
    assert [r["outcome"] for r in result["results"]] == ["started", "failed", "started"]


def test_quota_stops_remaining_items():
    client = _client()

    def start(nb, eid, **kw):
        if eid == "el-b":
            raise ResourceExhaustedError("quota")
        return _ok(eid)

    client.start_artifact_generation.side_effect = start
    result = generate_report_elements(client, "nb", "rep", PLAN, _sleep=lambda *_: None)
    assert [r["outcome"] for r in result["results"]] == ["started", "failed", "not_started"]
    assert result["stopped_reason"] == "quota"
    assert client.start_artifact_generation.call_count == 2


def test_auth_failure_stops_remaining_items():
    client = _client()
    client.start_artifact_generation.side_effect = ClientAuthenticationError("expired")
    result = generate_report_elements(client, "nb", "rep", PLAN, _sleep=lambda *_: None)
    assert result["stopped_reason"] == "auth"
    assert client.start_artifact_generation.call_count == 1


def test_unknown_outcome_reconciles_to_started_without_resend():
    client = _client()

    def start(nb, eid, **kw):
        client._state[eid]["status"] = "queued"  # Google accepted it
        raise KickoffOutcomeUnknownError("lost")

    client.start_artifact_generation.side_effect = start
    result = generate_report_elements(client, "nb", "rep", [PLAN[0]], _sleep=lambda *_: None)
    assert result["results"][0]["outcome"] == "started"
    assert client.start_artifact_generation.call_count == 1


def test_unknown_outcome_stays_unknown_and_is_never_resent():
    client = _client()
    client.start_artifact_generation.side_effect = KickoffOutcomeUnknownError("lost")
    result = generate_report_elements(client, "nb", "rep", [PLAN[0]], _sleep=lambda *_: None)
    assert result["results"][0]["outcome"] == "unknown"
    assert client.start_artifact_generation.call_count == 1


def test_started_elsewhere_after_validation_is_recorded_as_failed():
    client = _client()

    def start(nb, eid, **kw):
        if eid == "el-a":
            raise RPCError("already running", error_code=9)
        return _ok(eid)

    client.start_artifact_generation.side_effect = start
    result = generate_report_elements(client, "nb", "rep", PLAN, _sleep=lambda *_: None)
    assert result["results"][0]["outcome"] == "failed"
    assert result["counts"]["started"] == 2


def test_element_lock_blocks_overlap():
    from notebooklm_tools.services import interactive_reports as ir

    client = _client()
    client.start_artifact_generation.side_effect = lambda nb, eid, **kw: _ok(eid)
    lock = ir._element_lock("el-a")
    lock.acquire()
    try:
        result = generate_report_elements(client, "nb", "rep", [PLAN[0]], _sleep=lambda *_: None)
    finally:
        lock.release()
    assert result["results"][0]["outcome"] == "failed"
    assert "in progress" in result["results"][0]["error"]
    client.start_artifact_generation.assert_not_called()


def test_single_generation_uses_the_same_path():
    client = _client()
    client.start_artifact_generation.side_effect = lambda nb, eid, **kw: _ok(eid)
    result = generate_report_element(
        client, "nb", "rep", element_type="quiz", settings={"difficulty": "hard"}
    )
    assert result["outcome"] == "started"
    assert client.start_artifact_generation.call_args.kwargs["settings"] == {"difficulty": 3}


def test_single_generation_refuses_completed_element():
    import pytest

    from notebooklm_tools.services.errors import ValidationError

    client = _client(elements={"el-a": {"type": "quiz", "status": "completed", "title": "A"}})
    with pytest.raises(ValidationError):
        generate_report_element(client, "nb", "rep", element_id="el-a")
    client.start_artifact_generation.assert_not_called()


def test_second_run_of_same_plan_does_not_restart_element():
    from notebooklm_tools.services.interactive_reports import (
        execute_element_plan,
        prepare_element_plan,
    )

    client = _client()

    def start(nb, eid, **kw):
        client._state[eid]["status"] = "queued"  # Google accepted it
        return _ok(eid)

    client.start_artifact_generation.side_effect = start
    plan = prepare_element_plan(client, "nb", "rep", [PLAN[0]])  # both callers validated first
    first = execute_element_plan(client, "nb", plan, _sleep=lambda *_: None)
    second = execute_element_plan(client, "nb", plan, _sleep=lambda *_: None)

    assert first["results"][0]["outcome"] == "started"
    assert second["results"][0]["outcome"] == "failed"
    assert second["results"][0]["error_category"] == "not_suggested"
    assert client.start_artifact_generation.call_count == 1
