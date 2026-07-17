from notebooklm_tools.core.utils import (
    RPC_NAMES,
    extract_cookies_from_chrome_export,
    is_mind_map_json,
    parse_timestamp,
)


def test_parse_timestamp_valid():
    result = parse_timestamp([1700000000, 0])
    assert result == "2023-11-14T22:13:20Z"


def test_parse_timestamp_none():
    assert parse_timestamp(None) is None


def test_extract_cookies_header_string():
    result = extract_cookies_from_chrome_export("name=value; other=foo")
    assert result == {"name": "value", "other": "foo"}


def test_extract_cookies_from_chrome_export_list_prefers_google_com():
    export = [
        {"name": "SID", "value": "vn", "domain": ".google.com.vn"},
        {"name": "SID", "value": "google", "domain": ".google.com"},
        {"name": "SID", "value": "youtube", "domain": ".youtube.com"},
    ]

    assert extract_cookies_from_chrome_export(export)["SID"] == "google"


def test_extract_cookies_from_chrome_export_json_list_prefers_google_com():
    import json as _json

    export = _json.dumps(
        [
            {"name": "HSID", "value": "youtube", "domain": ".youtube.com"},
            {"name": "HSID", "value": "google", "domain": ".google.com"},
        ]
    )

    assert extract_cookies_from_chrome_export(export)["HSID"] == "google"


def test_rpc_names_exists():
    assert "wXbhsf" in RPC_NAMES


class TestIsMindMapJson:
    def test_children_key_is_mind_map(self):
        assert is_mind_map_json('{"name": "Root", "children": []}') is True

    def test_nodes_key_is_mind_map(self):
        assert is_mind_map_json('{"nodes": []}') is True

    def test_prose_note_is_not_mind_map(self):
        assert is_mind_map_json("To run Docling locally, follow these steps...") is False

    def test_json_without_mind_map_keys_is_not_mind_map(self):
        assert is_mind_map_json('{"name": "just a dict"}') is False

    def test_json_list_is_not_mind_map(self):
        assert is_mind_map_json('[{"children": []}]') is False

    def test_empty_and_none_are_not_mind_maps(self):
        assert is_mind_map_json("") is False
        assert is_mind_map_json(None) is False
