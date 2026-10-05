"""While a session profile switch is active (and several profiles exist), every tool result
says which account is in use, so a switch can never go unnoticed in another chat."""

import asyncio

import pytest

from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.mcp.tools import _utils
from notebooklm_tools.services import profiles
from notebooklm_tools.utils import config as cfg

_TEMP_TOOLS = ("_probe", "_aprobe")


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch, fake_credential_store):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / "storage"))
    for var in ("NLM_PROFILE", "NOTEBOOKLM_COOKIES", "NLM_AUTH_STORAGE"):
        monkeypatch.delenv(var, raising=False)
    cfg.set_session_profile(None)
    AuthManager("default").save_profile(cookies={"SID": "d"}, email="d@example.com")
    yield
    cfg.set_session_profile(None)
    _utils._tool_registry[:] = [t for t in _utils._tool_registry if t[0] not in _TEMP_TOOLS]


def _add_second_profile():
    AuthManager("work").save_profile(cookies={"SID": "w"}, email="w@example.com")


def test_no_note_without_a_switch_even_with_several_profiles():
    _add_second_profile()
    result = {"status": "success"}
    _utils.maybe_attach_active_profile_note(result, "notebook_list")
    assert "active_profile_note" not in result


def test_note_when_switched_and_several_profiles():
    _add_second_profile()
    profiles.switch_session_profile("work")
    result = {"status": "success"}
    _utils.maybe_attach_active_profile_note(result, "notebook_list")
    note = result["active_profile_note"]
    assert "'work'" in note and "'default'" in note


def test_no_note_with_a_single_profile():
    cfg.set_session_profile("default")  # switching to the only profile
    result = {"status": "success"}
    _utils.maybe_attach_active_profile_note(result, "notebook_list")
    assert "active_profile_note" not in result


def test_profile_tool_itself_is_not_annotated():
    _add_second_profile()
    profiles.switch_session_profile("work")
    result = {"status": "success"}
    _utils.maybe_attach_active_profile_note(result, "profile")
    assert "active_profile_note" not in result


def test_non_dict_results_are_left_alone():
    _add_second_profile()
    profiles.switch_session_profile("work")
    assert _utils.maybe_attach_active_profile_note("text", "notebook_list") is None


def test_logged_tool_attaches_note_sync_and_async():
    _add_second_profile()
    profiles.switch_session_profile("work")

    @_utils.logged_tool()
    def _probe() -> dict:
        return {"status": "success"}

    @_utils.logged_tool()
    async def _aprobe() -> dict:
        return {"status": "success"}

    assert "active_profile_note" in _probe()
    assert "active_profile_note" in asyncio.run(_aprobe())
