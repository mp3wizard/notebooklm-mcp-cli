import asyncio

import pytest

from notebooklm_tools.mcp.tools import _utils
from notebooklm_tools.mcp.tools import aliases as alias_tool

_TEMP_TOOLS = ("_probe", "_aprobe")


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / "storage"))
    from notebooklm_tools.utils.config import reset_config

    reset_config()
    yield
    # logged_tool() registers every decorated function; drop the test probes.
    _utils._tool_registry[:] = [t for t in _utils._tool_registry if t[0] not in _TEMP_TOOLS]


def test_alias_tool_set_list_get_delete():
    assert alias_tool.alias(action="set", name="nb", value="abc-123")["status"] == "success"
    assert alias_tool.alias(action="get", name="nb")["value"] == "abc-123"
    assert alias_tool.alias(action="list")["aliases"][0]["name"] == "nb"
    assert alias_tool.alias(action="delete", name="nb")["status"] == "success"
    assert alias_tool.alias(action="get", name="nb")["status"] == "error"


def test_logged_tool_resolves_notebook_id_keyword_and_positional():
    alias_tool.alias(action="set", name="nb", value="abc-123")
    seen = []

    @_utils.logged_tool()
    def _probe(notebook_id: str, other: str = "") -> dict:
        seen.append(notebook_id)
        return {"status": "success"}

    _probe(notebook_id="nb")
    _probe("nb")
    _probe(notebook_id="abc-123")
    _probe(notebook_id="something-else")
    assert seen == ["abc-123", "abc-123", "abc-123", "something-else"]


def test_logged_tool_resolves_notebook_id_async():
    alias_tool.alias(action="set", name="nb", value="abc-123")
    seen = []

    @_utils.logged_tool()
    async def _aprobe(notebook_id: str) -> dict:
        seen.append(notebook_id)
        return {"status": "success"}

    asyncio.run(_aprobe(notebook_id="nb"))
    assert seen == ["abc-123"]
