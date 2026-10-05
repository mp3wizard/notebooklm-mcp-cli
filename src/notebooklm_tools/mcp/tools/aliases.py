"""Alias tool - short names that stand in for notebook IDs."""

from ...services import ServiceError
from ...services import aliases as alias_service
from ._utils import ResultDict, error_result, logged_tool


@logged_tool()
def alias(
    action: str = "list", name: str = "", value: str = "", alias_type: str = "unknown"
) -> ResultDict:
    """Manage aliases: short names that stand in for notebook IDs.

    Once an alias exists, any tool's notebook_id can be the alias. Aliases are shared
    across all profiles.

    Args:
        action: list (default) | get | set | delete
        name: Alias name (get/set/delete).
        value: The real ID the alias points to (set).
        alias_type: Optional label, e.g. "notebook" (set).
    """
    try:
        if action == "list":
            return {"status": "success", "aliases": alias_service.list_aliases()}
        if action == "get":
            return {"status": "success", **alias_service.get_alias(name)}
        if action == "set":
            return {"status": "success", **alias_service.set_alias(name, value, alias_type)}
        if action == "delete":
            return {"status": "success", **alias_service.delete_alias(name)}
        return error_result(f"Unknown action '{action}'. Use list, get, set or delete.")
    except ServiceError as e:
        return error_result(e.user_message, hint=e.hint)
    except Exception as e:
        return error_result(str(e))
