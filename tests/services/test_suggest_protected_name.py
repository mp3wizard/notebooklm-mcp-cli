"""suggest_protected_name: a usable protected-mode name derived from an unusable one."""

import pytest

from notebooklm_tools.core.auth import AuthManager
from notebooklm_tools.services.auth_storage import suggest_protected_name
from notebooklm_tools.utils.config import reset_config


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch, fake_credential_store):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / "storage"))
    reset_config()


@pytest.mark.parametrize(
    "name, expected",
    [
        ("my work", "my-work"),
        ("john@work.com", "john-work.com"),
        ("  spaced  out  ", "spaced-out"),
        ("Work (Red Hat)", "Work-Red-Hat"),
        ("-.-weird-.-", "weird"),
    ],
)
def test_suggests_a_valid_name(name, expected):
    assert suggest_protected_name(name) == expected


@pytest.mark.parametrize("name", ["@@@", "   ", "...", ""])
def test_no_suggestion_when_nothing_usable_is_left(name):
    assert suggest_protected_name(name) is None


def test_no_suggestion_when_the_suggested_name_is_taken():
    AuthManager("my-work").save_profile(cookies={"SID": "w"}, email="w@example.com")
    assert suggest_protected_name("my work") is None


def test_no_suggestion_when_it_would_collide_ignoring_case():
    AuthManager("My-Work").save_profile(cookies={"SID": "w"}, email="w@example.com")
    assert suggest_protected_name("my work") is None
