"""Headless browser auth requires a valid authenticated RPC payload."""

from types import SimpleNamespace

from notebooklm_tools.core.errors import RPCError
from notebooklm_tools.core.notebooks import NotebookMixin
from notebooklm_tools.utils import cdp


class FakeNotebookClient(NotebookMixin):
    rpc_result = None

    def __init__(self, **_kwargs):
        pass

    def _is_enterprise(self):
        return False

    def _call_rpc(self, *_args):
        return self.rpc_result

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _candidate():
    return SimpleNamespace(
        cookies={"SID": "synthetic"},
        csrf_token="test",
        session_id="test",
        build_label="",
        base_host="",
    )


def test_missing_payload_cannot_validate_candidate(monkeypatch):
    monkeypatch.setattr("notebooklm_tools.core.client.NotebookLMClient", FakeNotebookClient)
    FakeNotebookClient.rpc_result = None
    assert FakeNotebookClient().list_notebooks() == []
    with __import__("pytest").raises(RPCError):
        FakeNotebookClient().list_notebooks(require_valid_response=True)
    assert cdp._validate_headless_candidate(_candidate(), "synthetic") is False


def test_valid_empty_notebook_list_is_accepted(monkeypatch):
    monkeypatch.setattr("notebooklm_tools.core.client.NotebookLMClient", FakeNotebookClient)
    FakeNotebookClient.rpc_result = []
    assert cdp._validate_headless_candidate(_candidate(), "synthetic") is True
