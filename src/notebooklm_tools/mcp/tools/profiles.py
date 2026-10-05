"""Profile tool - list saved Google accounts and choose which one this MCP server uses."""

from ...services import ServiceError
from ...services import profiles as profile_service
from ._utils import ResultDict, error_result, logged_tool


@logged_tool()
def profile(action: str = "list", name: str = "", make_default: bool = False) -> ResultDict:
    """List saved Google accounts (profiles) and choose which one to use.

    Args:
        action: list (default) | status | switch
            - list: every saved profile with email, storage mode, and which is active
            - status: storage details for `name` (or the active profile); metadata only
            - switch: use profile `name` for every later tool call until this MCP server
              restarts. In apps that share one server across chats (e.g. Claude Desktop),
              other open chats switch too.
        name: Profile name for status / switch.
        make_default: Only with action="switch". False (default) leaves the saved default
            alone. True ALSO makes it the saved default for the CLI and every future
            session - only when the user explicitly asks to change their default account.
    """
    try:
        if action == "list":
            return {
                "status": "success",
                "active": profile_service.get_active_profile(),
                "profiles": profile_service.list_profiles(),
            }
        if action == "status":
            return {
                "status": "success",
                "active": profile_service.get_active_profile(),
                "storage": profile_service.profile_storage_status(name or None),
            }
        if action == "switch":
            if not name:
                return error_result("name is required for action='switch'")
            result = (
                profile_service.make_default_profile(name)
                if make_default
                else profile_service.switch_session_profile(name)
            )
            return {"status": "success", **result}
        return error_result(f"Unknown action '{action}'. Use list, status or switch.")
    except ServiceError as e:
        return error_result(e.user_message, hint=e.hint)
    except Exception as e:
        return error_result(str(e))
