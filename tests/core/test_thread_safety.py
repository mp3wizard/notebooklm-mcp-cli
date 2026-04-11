# tests/core/test_thread_safety.py
"""Tests for thread-safety of NotebookLMClient shared state.

FastMCP dispatches sync tool functions into a thread pool, so concurrent
MCP tool calls share the same NotebookLMClient singleton. These tests
verify that the internal locking prevents race conditions.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch


def _make_client():
    """Create a NotebookLMClient with mocked auth (no network)."""
    from notebooklm_tools.core.base import BaseClient
    from notebooklm_tools.core.client import NotebookLMClient

    with patch.object(BaseClient, "_refresh_auth_tokens"):
        return NotebookLMClient(cookies={"test": "cookie"}, csrf_token="test_token")


class TestReqidCounter:
    """Verify _reqid_counter produces unique values under concurrent access."""

    def test_sequential_uniqueness(self):
        client = _make_client()
        values = set()
        for _ in range(100):
            with client._state_lock:
                client._reqid_counter += 100000
                values.add(client._reqid_counter)
        assert len(values) == 100

    def test_concurrent_uniqueness(self):
        client = _make_client()
        results = []

        def increment():
            with client._state_lock:
                client._reqid_counter += 100000
                return client._reqid_counter

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(increment) for _ in range(200)]
            for f in as_completed(futures):
                results.append(f.result())

        # All 200 values must be unique
        assert len(set(results)) == 200


class TestConversationCache:
    """Verify _conversation_cache operations are safe under concurrent writes."""

    def test_concurrent_cache_turns(self):
        client = _make_client()
        conv_id = "test-conv"

        def cache_turn(i):
            client._cache_conversation_turn(conv_id, f"q{i}", f"a{i}")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(cache_turn, i) for i in range(50)]
            for f in as_completed(futures):
                f.result()  # raise if any failed

        # All 50 turns should be present
        turns = client._conversation_cache[conv_id]
        assert len(turns) == 50
        # Turn numbers should be 1..50 (unique, sequential)
        turn_numbers = sorted(t.turn_number for t in turns)
        assert turn_numbers == list(range(1, 51))

    def test_concurrent_different_conversations(self):
        client = _make_client()

        def cache_turn(conv_idx, turn_idx):
            conv_id = f"conv-{conv_idx}"
            client._cache_conversation_turn(conv_id, f"q{turn_idx}", f"a{turn_idx}")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for conv in range(5):
                for turn in range(20):
                    futures.append(executor.submit(cache_turn, conv, turn))
            for f in as_completed(futures):
                f.result()

        # Each conversation should have exactly 20 turns
        for conv in range(5):
            assert len(client._conversation_cache[f"conv-{conv}"]) == 20

    def test_concurrent_clear_and_write(self):
        client = _make_client()
        conv_id = "test-conv"

        # Pre-populate
        client._cache_conversation_turn(conv_id, "q0", "a0")

        errors = []

        def writer():
            try:
                for i in range(20):
                    client._cache_conversation_turn(conv_id, f"q{i}", f"a{i}")
            except Exception as e:
                errors.append(e)

        def clearer():
            try:
                for _ in range(5):
                    client.clear_conversation(conv_id)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(writer) for _ in range(2)]
            futures.append(executor.submit(clearer))
            for f in as_completed(futures):
                f.result()

        # No exceptions should have been raised
        assert not errors


class TestGetClient:
    """Verify _get_client double-checked locking."""

    def test_concurrent_client_creation(self):
        client = _make_client()
        assert client._client is None

        results = []

        def get():
            return id(client._get_client())

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get) for _ in range(20)]
            for f in as_completed(futures):
                results.append(f.result())

        # All threads should get the same httpx.Client instance
        assert len(set(results)) == 1


class TestSourceRpcVersion:
    """Verify _source_rpc_version is safely read/written."""

    def test_concurrent_version_write(self):
        client = _make_client()
        assert client._source_rpc_version is None

        def set_version(version):
            with client._state_lock:
                if client._source_rpc_version is None:
                    client._source_rpc_version = version

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(set_version, "v1") for _ in range(20)]
            for f in as_completed(futures):
                f.result()

        # Should be set exactly once
        assert client._source_rpc_version == "v1"
