"""Alias management for NotebookLM CLI."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from filelock import FileLock

from notebooklm_tools.utils.config import get_config_dir


class AliasEntry:
    """Represents an alias with its value and type."""

    def __init__(self, value: str, alias_type: str = "unknown") -> None:
        self.value = value
        self.type = alias_type

    def to_dict(self) -> dict[str, str]:
        return {"value": self.value, "type": self.type}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | str) -> "AliasEntry":
        """Create from dict or legacy string format."""
        if isinstance(data, str):
            # Legacy format: just the value
            return cls(value=data, alias_type="unknown")
        return cls(value=data.get("value", ""), alias_type=data.get("type", "unknown"))


class AliasManager:
    """Manages user-defined aliases for IDs."""

    def __init__(self) -> None:
        self.config_dir = get_config_dir()
        self.aliases_file = self.config_dir / "aliases.json"
        self.lock_file = self.config_dir / "locks" / "aliases.lock"
        self._aliases: dict[str, AliasEntry] = {}
        self._load()

    def _lock(self) -> FileLock:
        """Return the cross-process lock guarding aliases.json."""
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        return FileLock(self.lock_file)

    def _load_unlocked(self) -> None:
        """Load aliases from disk. Caller must hold the alias lock."""
        if not self.aliases_file.exists():
            self._aliases = {}
            return

        try:
            content = self.aliases_file.read_text(encoding="utf-8")
            if not content:
                self._aliases = {}
                return
            raw_data = json.loads(content)
            self._aliases = {name: AliasEntry.from_dict(data) for name, data in raw_data.items()}
        except (OSError, json.JSONDecodeError, TypeError, ValueError, AttributeError):
            self._aliases = {}

    def _load(self) -> None:
        """Refresh aliases from disk under the cross-process lock.

        Reads still work (unlocked) when the lock file cannot be created,
        e.g. on a read-only config directory.
        """
        try:
            with self._lock():
                self._load_unlocked()
        except OSError:
            self._load_unlocked()

    def _save_unlocked(self) -> None:
        """Atomically save aliases. Caller must hold the alias lock."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        data = {name: entry.to_dict() for name, entry in self._aliases.items()}
        fd, temp_name = tempfile.mkstemp(
            dir=self.config_dir,
            prefix=".aliases-",
            suffix=".tmp",
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, self.aliases_file)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def set_alias(self, name: str, value: str, alias_type: str = "unknown") -> None:
        """Set an alias without losing concurrent updates from another process."""
        with self._lock():
            self._load_unlocked()
            self._aliases[name] = AliasEntry(value=value, alias_type=alias_type)
            self._save_unlocked()

    def get_alias(self, name: str) -> str | None:
        """Get an alias value from the latest on-disk state."""
        self._load()
        entry = self._aliases.get(name)
        return entry.value if entry else None

    def get_entry(self, name: str) -> AliasEntry | None:
        """Get the full alias entry including type."""
        self._load()
        return self._aliases.get(name)

    def delete_alias(self, name: str) -> bool:
        """Delete an alias without clobbering concurrent updates."""
        with self._lock():
            self._load_unlocked()
            if name not in self._aliases:
                return False
            del self._aliases[name]
            self._save_unlocked()
            return True

    def list_aliases(self) -> dict[str, AliasEntry]:
        """List the latest aliases with their types."""
        self._load()
        return self._aliases.copy()

    def resolve(self, id_or_alias: str) -> str:
        """
        Resolve an ID or alias to its value.
        If the input matches a known alias, return the aliased value.
        Otherwise return the input as-is.
        """
        self._load()
        entry = self._aliases.get(id_or_alias)
        return entry.value if entry else id_or_alias


# Global instance
_alias_manager: AliasManager | None = None


def get_alias_manager() -> AliasManager:
    """Get the global alias manager instance."""
    global _alias_manager
    if _alias_manager is None:
        _alias_manager = AliasManager()
    return _alias_manager


def detect_id_type(value: str, profile: str | None = None) -> str:
    """
    Detect the type of an ID by trying API calls.

    Returns: "notebook", "source", or "unknown"
    """
    from notebooklm_tools.cli.utils import get_client
    from notebooklm_tools.core.exceptions import NLMError
    from notebooklm_tools.services.errors import ServiceError
    from notebooklm_tools.services.sources import get_source_content

    try:
        with get_client(profile) as client:
            # Try as notebook ID first (most common)
            try:
                notebook = client.get_notebook(value)
                if notebook:
                    return "notebook"
            except NLMError:
                pass

            # Try as source ID
            try:
                # Reuse the supported source-content path instead of calling a
                # non-existent legacy client method.
                content = get_source_content(client, value)
                if content:
                    return "source"
            except (NLMError, ServiceError, AttributeError):
                pass

    except NLMError:
        pass

    return "unknown"
