"""Tests for runtime RPC-ID override mechanism."""

import json
from unittest.mock import patch

from notebooklm_tools.core.base import BaseClient, load_rpc_overrides


def test_load_rpc_overrides_empty(monkeypatch):
    monkeypatch.delenv("NOTEBOOKLM_RPC_OVERRIDES", raising=False)
    assert load_rpc_overrides() == {}


def test_load_rpc_overrides_valid(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_RPC_OVERRIDES", json.dumps({"RPC_LIST_NOTEBOOKS": "newId"}))
    assert load_rpc_overrides() == {"RPC_LIST_NOTEBOOKS": "newId"}


def test_load_rpc_overrides_malformed_returns_empty(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_RPC_OVERRIDES", "{not json")
    assert load_rpc_overrides() == {}


def test_load_rpc_overrides_non_object_returns_empty(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_RPC_OVERRIDES", json.dumps(["a", "b"]))
    assert load_rpc_overrides() == {}


def test_apply_rpc_overrides_known_attr(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_RPC_OVERRIDES", json.dumps({"RPC_LIST_NOTEBOOKS": "newId"}))
    with patch.object(BaseClient, "_refresh_auth_tokens"):
        client = BaseClient(cookies={"x": "y"}, csrf_token="t")
    assert client.RPC_LIST_NOTEBOOKS == "newId"
    assert BaseClient.RPC_LIST_NOTEBOOKS == "wXbhsf"  # class attr untouched


def test_apply_rpc_overrides_unknown_attr_ignored(monkeypatch):
    monkeypatch.setenv(
        "NOTEBOOKLM_RPC_OVERRIDES", json.dumps({"RPC_DOES_NOT_EXIST": "z", "NOT_AN_RPC": "z"})
    )
    with patch.object(BaseClient, "_refresh_auth_tokens"):
        client = BaseClient(cookies={"x": "y"}, csrf_token="t")
    assert not hasattr(client, "RPC_DOES_NOT_EXIST")
