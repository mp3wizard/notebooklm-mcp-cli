"""Tests for smart_select service — tag management and intelligent notebook selection."""

import json
import threading
from unittest.mock import patch

import pytest

from notebooklm_tools.services.errors import NotFoundError, ValidationError
from notebooklm_tools.services.smart_select import (
    _get_tags_lock,
    _save_tags_unlocked,
    smart_select,
    tag_add,
    tag_list,
    tag_remove,
)


@pytest.fixture
def tags_dir(tmp_path):
    """Provide a temporary tags storage directory."""
    with patch("notebooklm_tools.services.smart_select.get_storage_dir", return_value=tmp_path):
        yield tmp_path


class TestTagAdd:
    def test_add_tags_to_new_notebook(self, tags_dir):
        result = tag_add("nb-001", ["ai", "research"], "AI Research")
        assert result["notebook_id"] == "nb-001"
        assert result["notebook_title"] == "AI Research"
        assert set(result["tags"]) == {"ai", "research"}

    def test_add_tags_to_existing_notebook(self, tags_dir):
        tag_add("nb-001", ["ai"], "AI Research")
        result = tag_add("nb-001", ["mcp", "tools"])
        assert set(result["tags"]) == {"ai", "mcp", "tools"}

    def test_add_duplicate_tags(self, tags_dir):
        tag_add("nb-001", ["ai", "research"])
        result = tag_add("nb-001", ["ai", "llm"])
        assert sorted(result["tags"]) == ["ai", "llm", "research"]

    def test_add_tags_normalizes_case(self, tags_dir):
        result = tag_add("nb-001", ["AI", "Research", "LLM"])
        assert result["tags"] == ["ai", "llm", "research"]

    def test_add_tags_strips_whitespace(self, tags_dir):
        result = tag_add("nb-001", ["  ai  ", " research "])
        assert result["tags"] == ["ai", "research"]

    def test_add_empty_tags_raises(self, tags_dir):
        with pytest.raises(ValidationError):
            tag_add("nb-001", [])

    def test_add_only_whitespace_tags_raises(self, tags_dir):
        with pytest.raises(ValidationError):
            tag_add("nb-001", ["  ", ""])

    def test_add_updates_title(self, tags_dir):
        tag_add("nb-001", ["ai"], "Old Title")
        result = tag_add("nb-001", ["mcp"], "New Title")
        assert result["notebook_title"] == "New Title"

    def test_add_preserves_title_if_empty(self, tags_dir):
        tag_add("nb-001", ["ai"], "My Notebook")
        result = tag_add("nb-001", ["mcp"])
        assert result["notebook_title"] == "My Notebook"


class TestTagRemove:
    def test_remove_tags(self, tags_dir):
        tag_add("nb-001", ["ai", "research", "mcp"])
        result = tag_remove("nb-001", ["research"])
        assert set(result["tags"]) == {"ai", "mcp"}

    def test_remove_all_tags(self, tags_dir):
        tag_add("nb-001", ["ai", "research"])
        result = tag_remove("nb-001", ["ai", "research"])
        assert result["tags"] == []

    def test_remove_nonexistent_tag_is_safe(self, tags_dir):
        tag_add("nb-001", ["ai"])
        result = tag_remove("nb-001", ["nonexistent"])
        assert result["tags"] == ["ai"]

    def test_remove_from_untagged_notebook_raises(self, tags_dir):
        with pytest.raises(NotFoundError):
            tag_remove("nb-999", ["ai"])


class TestTagList:
    def test_list_empty(self, tags_dir):
        result = tag_list()
        assert result["count"] == 0
        assert result["entries"] == []

    def test_list_with_entries(self, tags_dir):
        tag_add("nb-001", ["ai"], "AI Research")
        tag_add("nb-002", ["dev"], "Dev Tools")
        result = tag_list()
        assert result["count"] == 2
        assert len(result["entries"]) == 2


class TestSmartSelect:
    def test_select_by_single_tag(self, tags_dir):
        tag_add("nb-001", ["ai", "research"], "AI Research")
        tag_add("nb-002", ["dev", "tools"], "Dev Tools")
        result = smart_select("ai")
        assert result["count"] == 1
        assert result["matched_notebooks"][0]["notebook_id"] == "nb-001"

    def test_select_by_multiple_tags(self, tags_dir):
        tag_add("nb-001", ["ai", "research", "mcp"], "AI Research")
        tag_add("nb-002", ["ai", "tools"], "Dev Tools")
        result = smart_select("ai mcp")
        assert result["count"] == 2
        assert result["matched_notebooks"][0]["notebook_id"] == "nb-001"  # 2 matches
        assert result["matched_notebooks"][1]["notebook_id"] == "nb-002"  # 1 match

    def test_select_with_commas(self, tags_dir):
        tag_add("nb-001", ["ai", "mcp"], "AI")
        result = smart_select("ai,mcp")
        assert result["count"] == 1

    def test_select_no_matches(self, tags_dir):
        tag_add("nb-001", ["ai"], "AI")
        result = smart_select("finance")
        assert result["count"] == 0

    def test_select_empty_tags_db(self, tags_dir):
        result = smart_select("anything")
        assert result["count"] == 0

    def test_select_empty_query_raises(self, tags_dir):
        with pytest.raises(ValidationError):
            smart_select("")

    def test_select_case_insensitive(self, tags_dir):
        tag_add("nb-001", ["ai", "research"])
        result = smart_select("AI Research")
        assert result["count"] == 1

    def test_select_ranked_by_match_count(self, tags_dir):
        tag_add("nb-001", ["ai", "mcp", "tools"], "All Three")
        tag_add("nb-002", ["ai", "mcp"], "Two")
        tag_add("nb-003", ["ai"], "One")
        result = smart_select("ai mcp tools")
        assert result["count"] == 3
        assert result["matched_notebooks"][0]["notebook_id"] == "nb-001"
        assert result["matched_notebooks"][1]["notebook_id"] == "nb-002"
        assert result["matched_notebooks"][2]["notebook_id"] == "nb-003"


class TestPersistence:
    def test_waiting_writer_reloads_latest_state_before_mutation(self, tags_dir):
        path = tags_dir / "tags.json"
        started = threading.Event()
        errors: list[Exception] = []

        def writer() -> None:
            started.set()
            try:
                tag_add("nb-002", ["beta"], "Second")
            except Exception as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        with _get_tags_lock(path):
            thread = threading.Thread(target=writer)
            thread.start()
            assert started.wait(timeout=1)
            thread.join(timeout=0.05)
            assert thread.is_alive()
            _save_tags_unlocked(
                path,
                {
                    "nb-001": {
                        "notebook_id": "nb-001",
                        "notebook_title": "First",
                        "tags": ["alpha"],
                    }
                },
            )

        thread.join(timeout=2)
        assert not thread.is_alive()
        assert errors == []
        entries = {entry["notebook_id"]: entry for entry in tag_list()["entries"]}
        assert set(entries) == {"nb-001", "nb-002"}
        assert entries["nb-001"]["tags"] == ["alpha"]
        assert entries["nb-002"]["tags"] == ["beta"]

    def test_tags_persist_to_disk(self, tags_dir):
        tag_add("nb-001", ["ai"], "AI")
        path = tags_dir / "tags.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert "nb-001" in data

    def test_tags_load_from_disk(self, tags_dir):
        tag_add("nb-001", ["ai"], "AI")
        result = tag_list()
        assert result["count"] == 1

    def test_handles_corrupted_file(self, tags_dir):
        path = tags_dir / "tags.json"
        path.write_text("not valid json")
        result = tag_list()
        assert result["count"] == 0

    def test_handles_missing_file(self, tags_dir):
        result = tag_list()
        assert result["count"] == 0
