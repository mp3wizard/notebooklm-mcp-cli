import pytest

from notebooklm_tools.services import aliases
from notebooklm_tools.services.errors import NotFoundError, ServiceError, ValidationError

UUID = "12345678-1234-1234-1234-123456789abc"


@pytest.fixture(autouse=True)
def setup_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_MCP_CLI_PATH", str(tmp_path / "storage"))
    from notebooklm_tools.utils.config import reset_config

    reset_config()


def test_set_get_list_delete_roundtrip():
    aliases.set_alias("work-nb", "abc-123", "notebook")
    assert aliases.get_alias("work-nb")["value"] == "abc-123"
    assert aliases.list_aliases() == [{"name": "work-nb", "value": "abc-123", "type": "notebook"}]
    aliases.delete_alias("work-nb")
    assert aliases.list_aliases() == []


def test_get_and_delete_missing_alias_raise_not_found():
    with pytest.raises(NotFoundError):
        aliases.get_alias("nope")
    with pytest.raises(NotFoundError):
        aliases.delete_alias("nope")


def test_empty_name_or_value_rejected():
    with pytest.raises(ValidationError):
        aliases.set_alias("", "x")
    with pytest.raises(ValidationError):
        aliases.set_alias("x", "")


def test_alias_cannot_look_like_a_uuid():
    with pytest.raises(ValidationError):
        aliases.set_alias(UUID, "other")


def test_resolve_passes_unknown_and_real_ids_through():
    aliases.set_alias("work-nb", "abc-123")
    assert aliases.resolve("work-nb") == "abc-123"
    assert aliases.resolve(UUID) == UUID
    assert aliases.resolve("unknown") == "unknown"


def test_alias_written_by_another_process_is_seen_immediately():
    from notebooklm_tools.core.alias import AliasManager

    AliasManager().set_alias("late", "xyz")  # simulates `nlm alias set` in another process
    assert aliases.resolve("late") == "xyz"


def test_stale_alias_managers_preserve_each_others_updates(tmp_path, monkeypatch):
    from notebooklm_tools.core import alias as alias_core

    monkeypatch.setattr(alias_core, "get_config_dir", lambda: tmp_path)
    first = alias_core.AliasManager()
    second = alias_core.AliasManager()

    first.set_alias("alpha", "a")
    second.set_alias("beta", "b")

    assert alias_core.AliasManager().get_alias("alpha") == "a"
    assert alias_core.AliasManager().get_alias("beta") == "b"


def test_long_lived_alias_manager_refreshes_before_reads(tmp_path, monkeypatch):
    from notebooklm_tools.core import alias as alias_core

    monkeypatch.setattr(alias_core, "get_config_dir", lambda: tmp_path)
    long_lived = alias_core.AliasManager()
    alias_core.AliasManager().set_alias("late", "xyz")

    assert long_lived.resolve("late") == "xyz"
    assert long_lived.get_alias("late") == "xyz"


def test_write_failure_becomes_service_error(monkeypatch):
    def boom(self, *a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("notebooklm_tools.core.alias.AliasManager.set_alias", boom)
    with pytest.raises(ServiceError, match="Could not save aliases"):
        aliases.set_alias("x", "y")


@pytest.mark.parametrize("content", ["[]", '{"a": 5}', '{"a": ["x"]}'])
def test_unexpected_aliases_file_shape_resets_instead_of_crashing(tmp_path, monkeypatch, content):
    from notebooklm_tools.core import alias as alias_core

    monkeypatch.setattr(alias_core, "get_config_dir", lambda: tmp_path)
    (tmp_path / "aliases.json").write_text(content, encoding="utf-8")

    assert alias_core.AliasManager().resolve("a") == "a"


def test_alias_reads_work_when_lock_file_cannot_be_created(tmp_path, monkeypatch):
    from notebooklm_tools.core import alias as alias_core

    monkeypatch.setattr(alias_core, "get_config_dir", lambda: tmp_path)
    alias_core.AliasManager().set_alias("alpha", "a")

    def read_only(self):
        raise PermissionError("read-only config dir")

    monkeypatch.setattr(alias_core.AliasManager, "_lock", read_only)

    assert alias_core.AliasManager().resolve("alpha") == "a"
