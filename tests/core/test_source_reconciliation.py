"""Tests for source reconciliation logic (Issue #196).

Verifies that accepted-pending RPC errors (code 3 / code 9) are resolved
by polling the notebook source list instead of surfacing as false-negative
failures to the caller.
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

from notebooklm_tools.core.errors import RPCError
from notebooklm_tools.core.sources import SourceMixin

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOTEBOOK_ID = "nb-reconcile-test"
MOCK_TEXT_SOURCE = {"id": "src-text-001", "title": "My Text Source", "url": None}
MOCK_URL_SOURCE = {
    "id": "src-url-001",
    "title": "Example Page",
    "url": "https://example.com/page",
}
MOCK_DRIVE_SOURCE = {
    "id": "src-drive-001",
    "title": "My Drive Doc",
    "drive_doc_id": "drive-doc-abc",
}


def _rpc_error(code: int, msg: str = "INVALID_ARGUMENT") -> RPCError:
    return RPCError(message=msg, error_code=code)


def _make_client() -> SourceMixin:
    """Create a minimal SourceMixin with mocked internals."""
    with patch.object(SourceMixin, "__init__", lambda self: None):
        client = SourceMixin()
    client._source_rpc_version = None
    client._state_lock = threading.Lock()
    client._call_rpc = MagicMock()
    return client


# ---------------------------------------------------------------------------
# _reconcile_source helper
# ---------------------------------------------------------------------------


class TestReconcileSource:
    """Unit tests for the _reconcile_source helper method."""

    def test_returns_matched_source_immediately(self):
        """Finds matching source on first poll."""
        client = _make_client()
        client.get_notebook_sources_with_types = MagicMock(return_value=[MOCK_TEXT_SOURCE])

        result = client._reconcile_source(
            NOTEBOOK_ID,
            match_fn=lambda src: src.get("id") == "src-text-001",
        )

        assert result == MOCK_TEXT_SOURCE
        client.get_notebook_sources_with_types.assert_called_once_with(NOTEBOOK_ID)

    def test_retries_until_source_appears(self):
        """Retries when source not present initially, succeeds on second poll."""
        client = _make_client()
        # First call returns empty, second returns the source
        client.get_notebook_sources_with_types = MagicMock(side_effect=[[], [MOCK_TEXT_SOURCE]])

        result = client._reconcile_source(
            NOTEBOOK_ID,
            match_fn=lambda src: src.get("id") == "src-text-001",
            poll_attempts=3,
            poll_delay=0,  # no sleep in tests
        )

        assert result == MOCK_TEXT_SOURCE
        assert client.get_notebook_sources_with_types.call_count == 2

    def test_returns_none_when_source_never_appears(self):
        """Returns None after exhausting all poll attempts."""
        client = _make_client()
        client.get_notebook_sources_with_types = MagicMock(return_value=[])

        result = client._reconcile_source(
            NOTEBOOK_ID,
            match_fn=lambda src: src.get("id") == "nonexistent",
            poll_attempts=3,
            poll_delay=0,
        )

        assert result is None
        assert client.get_notebook_sources_with_types.call_count == 3

    def test_survives_listing_exception(self):
        """Does not raise if get_notebook_sources_with_types itself fails."""
        client = _make_client()
        client.get_notebook_sources_with_types = MagicMock(
            side_effect=RuntimeError("network error")
        )

        result = client._reconcile_source(
            NOTEBOOK_ID,
            match_fn=lambda src: True,
            poll_attempts=2,
            poll_delay=0,
        )

        assert result is None


# ---------------------------------------------------------------------------
# add_text_source reconciliation
# ---------------------------------------------------------------------------


class TestAddTextSourceReconciliation:
    """add_text_source reconciles accepted-pending code 3/9 errors."""

    def test_code3_reconciles_to_success(self):
        """RPCError code 3 → source found via polling → success returned."""
        client = _make_client()
        client._call_rpc = MagicMock(side_effect=_rpc_error(3))
        client.get_notebook_sources_with_types = MagicMock(return_value=[MOCK_TEXT_SOURCE])

        result = client.add_text_source(NOTEBOOK_ID, text="Hello world", title="My Text Source")

        assert result is not None
        assert result["id"] == "src-text-001"

    def test_code9_reconciles_to_success(self):
        """RPCError code 9 → source found via polling → success returned."""
        client = _make_client()
        client._call_rpc = MagicMock(side_effect=_rpc_error(9, "FAILED_PRECONDITION"))
        client.get_notebook_sources_with_types = MagicMock(return_value=[MOCK_TEXT_SOURCE])

        result = client.add_text_source(NOTEBOOK_ID, text="Hello", title="My Text Source")

        assert result is not None
        assert result["id"] == "src-text-001"

    def test_code3_reraises_when_source_not_found(self):
        """RPCError code 3 → source NOT found → original error re-raised."""
        client = _make_client()
        err = _rpc_error(3)
        client._call_rpc = MagicMock(side_effect=err)
        client.get_notebook_sources_with_types = MagicMock(return_value=[])

        with pytest.raises(RPCError) as exc_info:
            client.add_text_source(NOTEBOOK_ID, text="Hello", title="Gone Source")

        assert exc_info.value.error_code == 3

    def test_real_error_code7_not_reconciled(self):
        """RPCError code 7 (PERMISSION_DENIED) always re-raises immediately."""
        client = _make_client()
        client._call_rpc = MagicMock(side_effect=_rpc_error(7, "PERMISSION_DENIED"))
        client.get_notebook_sources_with_types = MagicMock(return_value=[])

        with pytest.raises(RPCError) as exc_info:
            client.add_text_source(NOTEBOOK_ID, text="Hello", title="Test")

        assert exc_info.value.error_code == 7
        # Listing should NOT have been called for a real error
        client.get_notebook_sources_with_types.assert_not_called()


# ---------------------------------------------------------------------------
# add_drive_source reconciliation
# ---------------------------------------------------------------------------


class TestAddDriveSourceReconciliation:
    """add_drive_source reconciles accepted-pending code 3/9 errors."""

    def test_code3_reconciles_to_success(self):
        """RPCError code 3 → drive source found via polling → success returned."""
        client = _make_client()
        client._call_rpc = MagicMock(side_effect=_rpc_error(3))
        client.get_notebook_sources_with_types = MagicMock(return_value=[MOCK_DRIVE_SOURCE])

        result = client.add_drive_source(
            NOTEBOOK_ID,
            document_id="drive-doc-abc",
            title="My Drive Doc",
        )

        assert result is not None
        assert result["id"] == "src-drive-001"

    def test_real_error_reraises(self):
        """Real errors (code 7) are not swallowed."""
        client = _make_client()
        client._call_rpc = MagicMock(side_effect=_rpc_error(7))

        with pytest.raises(RPCError) as exc_info:
            client.add_drive_source(NOTEBOOK_ID, document_id="drive-doc-abc", title="Doc")

        assert exc_info.value.error_code == 7


# ---------------------------------------------------------------------------
# add_url_source: v1 accepted-pending → no double-submit
# ---------------------------------------------------------------------------


class TestAddUrlSourceReconciliation:
    """add_url_source reconciles before v1→v2 fallback."""

    def test_v1_accepted_pending_skips_v2(self):
        """v1 returns code 3 AND source found in notebook → v2 NOT called."""
        client = _make_client()
        client._add_url_source_v1 = MagicMock(side_effect=_rpc_error(3))
        client._add_url_source_v2 = MagicMock(return_value=None)
        client.get_notebook_sources_with_types = MagicMock(return_value=[MOCK_URL_SOURCE])

        result = client.add_url_source(NOTEBOOK_ID, "https://example.com/page")

        # Should succeed via reconciliation
        assert result is not None
        assert result["id"] == "src-url-001"
        # v2 must never be called — no double-submit
        client._add_url_source_v2.assert_not_called()
        # Version should be recorded as v1 (accepted it)
        assert client._source_rpc_version == "v1"

    def test_v1_genuinely_rejected_falls_through_to_v2(self):
        """v1 returns code 3 AND source NOT found → falls through to v2."""
        client = _make_client()
        mock_v2_result = [[[[["src-v2-001"], "V2 Source"]]]]
        client._add_url_source_v1 = MagicMock(side_effect=_rpc_error(3))
        client._add_url_source_v2 = MagicMock(return_value=mock_v2_result)
        client.get_notebook_sources_with_types = MagicMock(return_value=[])

        client.add_url_source(NOTEBOOK_ID, "https://example.com/page")  # noqa: F841

        client._add_url_source_v2.assert_called_once()
        assert client._source_rpc_version == "v2"
