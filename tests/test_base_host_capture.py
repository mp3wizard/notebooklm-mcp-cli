"""Regression tests for capturing the signed-in host during login (issue #269).

Google's "Gemini Notebook" rebrand redirects some migrated accounts to
notebook.google.com after sign-in. The CLI must record which host the
browser actually landed on so later API calls target the same host
(see notebooklm_tools.utils.config.get_base_url and BaseClient.base_host).
"""

from unittest.mock import patch

from notebooklm_tools.core.auth import AuthTokens
from notebooklm_tools.utils import cdp


class TestValidateHeadlessCandidate:
    def test_valid_candidate_uses_side_effect_free_client(self):
        tokens = AuthTokens(
            cookies={"SID": "fresh"},
            csrf_token="csrf",
            session_id="sid",
            build_label="bl",
            base_host="notebook.google.com",
        )

        with patch("notebooklm_tools.core.client.NotebookLMClient") as mock_client:
            client = mock_client.return_value.__enter__.return_value
            client.list_notebooks.return_value = []

            assert cdp._validate_headless_candidate(tokens, "work") is True

        mock_client.assert_called_once_with(
            cookies=tokens.cookies,
            csrf_token="csrf",
            session_id="sid",
            build_label="bl",
            base_host="notebook.google.com",
            profile_name="work",
            is_env_auth=True,
        )
        client.list_notebooks.assert_called_once_with()

    def test_invalid_candidate_is_rejected(self):
        tokens = AuthTokens(cookies={"SID": "fresh"}, csrf_token="csrf")

        with patch("notebooklm_tools.core.client.NotebookLMClient") as mock_client:
            client = mock_client.return_value.__enter__.return_value
            client.list_notebooks.side_effect = RuntimeError("unauthenticated")

            assert cdp._validate_headless_candidate(tokens, "work") is False


class TestRunHeadlessAuthCapturesBaseHost:
    def _run_with_current_url(
        self,
        current_url: str,
        profile_name: str = "default",
        valid_candidate: bool = True,
    ):
        with (
            patch.object(cdp, "has_chrome_profile", return_value=True),
            patch.object(
                cdp, "find_existing_nlm_chrome", return_value=(9223, "ws://127.0.0.1:9223")
            ),
            patch.object(
                cdp,
                "find_or_create_notebooklm_page",
                return_value={"webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1"},
            ),
            patch.object(cdp, "_normalize_ws_url", side_effect=lambda u: u),
            patch.object(cdp, "get_current_url", return_value=current_url),
            patch.object(cdp, "is_logged_in", return_value=True),
            patch.object(cdp, "_wait_for_page_ready", return_value=("<html></html>", True)),
            patch.object(
                cdp,
                "get_page_cookies",
                return_value=[
                    {"name": name, "value": "x"}
                    for name in ("SID", "HSID", "SSID", "APISID", "SAPISID")
                ],
            ),
            patch.object(cdp, "extract_csrf_token", return_value="csrf"),
            patch.object(cdp, "extract_session_id", return_value="sid"),
            patch.object(
                cdp,
                "_validate_headless_candidate",
                return_value=valid_candidate,
            ),
            patch.object(cdp, "cleanup_chrome_profile_cache", return_value=0),
            patch("notebooklm_tools.core.auth.save_tokens_to_cache") as mock_save,
        ):
            tokens = cdp.run_headless_auth(profile_name=profile_name)
            return tokens, mock_save

    def test_base_host_captured_on_rebrand_host(self):
        tokens, _ = self._run_with_current_url("https://notebook.google.com/notebook/abc")
        assert tokens is not None
        assert tokens.base_host == "notebook.google.com"

    def test_base_host_captured_on_legacy_host(self):
        tokens, _ = self._run_with_current_url("https://notebooklm.google.com/")
        assert tokens is not None
        assert tokens.base_host == "notebooklm.google.com"

    def test_named_profile_is_preserved_when_tokens_are_cached(self):
        tokens, mock_save = self._run_with_current_url(
            "https://notebooklm.google.com/",
            profile_name="tsm",
        )

        mock_save.assert_called_once_with(tokens, profile_name="tsm")

    def test_rpc_invalid_candidate_is_not_cached_or_returned(self):
        tokens, mock_save = self._run_with_current_url(
            "https://notebook.google.com/",
            profile_name="work",
            valid_candidate=False,
        )

        assert tokens is None
        mock_save.assert_not_called()
