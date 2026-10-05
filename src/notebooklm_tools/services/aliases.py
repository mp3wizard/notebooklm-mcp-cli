"""Alias CRUD for notebook/source IDs, shared by MCP (the CLI keeps using core.alias)."""

from __future__ import annotations

import re
from typing import Any

from notebooklm_tools.core.alias import AliasManager
from notebooklm_tools.services.errors import NotFoundError, ServiceError, ValidationError

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _mgr() -> AliasManager:
    """Fresh read of aliases.json each call so CLI edits are seen without a restart."""
    return AliasManager()


def _not_found(name: str) -> NotFoundError:
    return NotFoundError(
        f"Alias '{name}' not found.",
        hint="Use the alias tool with action='list'.",
        resource_type="alias",
    )


def list_aliases() -> list[dict[str, Any]]:
    return [
        {"name": n, "value": e.value, "type": e.type}
        for n, e in sorted(_mgr().list_aliases().items())
    ]


def set_alias(name: str, value: str, alias_type: str = "unknown") -> dict[str, Any]:
    name, value = (name or "").strip(), (value or "").strip()
    if not name or not value:
        raise ValidationError("Both name and value are required.")
    if _UUID.match(name):
        raise ValidationError("An alias cannot look like a real ID.")
    try:
        _mgr().set_alias(name, value, alias_type)
    except OSError as exc:
        raise ServiceError(f"Could not save aliases: {exc}") from exc
    return {"name": name, "value": value, "type": alias_type}


def get_alias(name: str) -> dict[str, Any]:
    entry = _mgr().get_entry(name)
    if entry is None:
        raise _not_found(name)
    return {"name": name, "value": entry.value, "type": entry.type}


def delete_alias(name: str) -> dict[str, Any]:
    try:
        deleted = _mgr().delete_alias(name)
    except OSError as exc:
        raise ServiceError(f"Could not save aliases: {exc}") from exc
    if not deleted:
        raise _not_found(name)
    return {"name": name, "deleted": True}


def resolve(id_or_alias: str) -> str:
    return _mgr().resolve(id_or_alias)
