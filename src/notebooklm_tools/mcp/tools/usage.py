"""Usage tools - plan allowance windows and subscription tier."""

from ...services import ServiceError
from ...services import usage as usage_service
from ._utils import ResultDict, error_result, get_client, logged_tool


@logged_tool()
def usage_get(profile: str | None = None) -> ResultDict:
    """Show how much of the plan's usage allowance is left, and when it resets.

    Gemini Notebook meters usage as compute against two windows at once: a short
    rolling window and a weekly one. Both are reported, each with the percentage
    used, the percentage remaining and the reset time in UTC.

    Args:
        profile: Saved account profile, e.g. "work" or "personal". Overrides
            environment cookies for this call without switching the default
            account. Omit to use the MCP server's current authentication.
    """
    try:
        if profile is not None:
            result = usage_service.get_usage_for_profile(profile)
        else:
            result = usage_service.get_usage(get_client())
        return {"status": "success", **result}
    except ServiceError as e:
        return error_result(e.user_message, hint=e.hint)
    except Exception as e:
        return error_result(str(e))
