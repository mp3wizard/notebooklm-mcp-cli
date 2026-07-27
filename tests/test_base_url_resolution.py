"""Regression tests for NotebookLM base-URL host resolution (issue #269).

Google is rolling out a rebrand of NotebookLM to "Gemini Notebook" at
notebook.google.com. Accounts migrated to the new host need:

1. `get_base_url()` to accept notebook.google.com via NOTEBOOKLM_BASE_URL.
2. `get_base_url()` to prefer a persisted per-profile `base_host` (the host
   the browser was last signed in on) over the hardcoded default, without
   overriding an explicit NOTEBOOKLM_BASE_URL.
3. BaseClient (and NotebookLMClient) to route requests to that host when
   constructed with `base_host=...`.
"""

import pytest

from notebooklm_tools.utils.config import _ALLOWED_BASE_HOSTS, get_base_url


class TestGetBaseUrlPrecedence:
    def test_default_when_nothing_set(self, monkeypatch):
        monkeypatch.delenv("NOTEBOOKLM_BASE_URL", raising=False)
        assert get_base_url() == "https://notebooklm.google.com"

    def test_profile_host_used_when_no_env_override(self, monkeypatch):
        monkeypatch.delenv("NOTEBOOKLM_BASE_URL", raising=False)
        assert get_base_url("notebook.google.com") == "https://notebook.google.com"

    def test_env_override_wins_over_profile_host(self, monkeypatch):
        monkeypatch.setenv("NOTEBOOKLM_BASE_URL", "https://notebooklm.cloud.google.com")
        assert get_base_url("notebook.google.com") == "https://notebooklm.cloud.google.com"

    def test_unknown_profile_host_falls_back_to_default(self, monkeypatch):
        monkeypatch.delenv("NOTEBOOKLM_BASE_URL", raising=False)
        assert get_base_url("evil.example.com") == "https://notebooklm.google.com"

    def test_empty_profile_host_falls_back_to_default(self, monkeypatch):
        monkeypatch.delenv("NOTEBOOKLM_BASE_URL", raising=False)
        assert get_base_url("") == "https://notebooklm.google.com"
        assert get_base_url(None) == "https://notebooklm.google.com"

    def test_env_override_accepts_new_rebrand_host(self, monkeypatch):
        monkeypatch.setenv("NOTEBOOKLM_BASE_URL", "https://notebook.google.com")
        assert get_base_url() == "https://notebook.google.com"

    def test_env_override_rejects_unknown_host(self, monkeypatch):
        monkeypatch.setenv("NOTEBOOKLM_BASE_URL", "https://evil.example.com")
        with pytest.raises(ValueError, match="must use https and one of"):
            get_base_url()

    def test_allowed_hosts_include_rebrand_host(self):
        assert "notebook.google.com" in _ALLOWED_BASE_HOSTS
        assert "notebooklm.google.com" in _ALLOWED_BASE_HOSTS


class TestBaseClientHostRouting:
    def test_client_uses_base_host_for_urls(self, monkeypatch):
        from notebooklm_tools.core.client import NotebookLMClient

        monkeypatch.delenv("NOTEBOOKLM_BASE_URL", raising=False)
        client = NotebookLMClient(
            cookies={"SID": "x"}, csrf_token="csrf", base_host="notebook.google.com"
        )
        try:
            assert client._get_base_url() == "https://notebook.google.com"
            assert client._get_batchexecute_url() == (
                "https://notebook.google.com/_/LabsTailwindUi/data/batchexecute"
            )
            assert client._get_upload_url() == "https://notebook.google.com/upload/_/"
        finally:
            client.close()

    def test_client_defaults_to_notebooklm_host(self, monkeypatch):
        from notebooklm_tools.core.client import NotebookLMClient

        monkeypatch.delenv("NOTEBOOKLM_BASE_URL", raising=False)
        client = NotebookLMClient(cookies={"SID": "x"}, csrf_token="csrf")
        try:
            assert client._get_base_url() == "https://notebooklm.google.com"
        finally:
            client.close()

    def test_client_env_override_wins_over_base_host(self, monkeypatch):
        from notebooklm_tools.core.client import NotebookLMClient

        monkeypatch.setenv("NOTEBOOKLM_BASE_URL", "https://notebooklm.cloud.google.com")
        client = NotebookLMClient(
            cookies={"SID": "x"}, csrf_token="csrf", base_host="notebook.google.com"
        )
        try:
            assert client._get_base_url() == "https://notebooklm.cloud.google.com"
        finally:
            client.close()
