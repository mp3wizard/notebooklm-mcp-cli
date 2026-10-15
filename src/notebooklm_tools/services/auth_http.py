"""HTTP-only renewal of eligible cookies and NotebookLM page tokens.

This does not renew Google's browser-dependent PSIDTS family and is not a
substitute for interactive login. No browser process is launched.
"""

from __future__ import annotations

import time
from typing import TypedDict

from notebooklm_tools.core.auth import AuthTokens, load_cached_tokens, save_tokens_to_cache
from notebooklm_tools.core.client import NotebookLMClient
from notebooklm_tools.core.credential_store import StaleRevisionError
from notebooklm_tools.services.errors import ConflictError, NotFoundError, ServiceError


class HttpRefreshResult(TypedDict):
    profile: str
    status: str


def refresh_auth_http_only(profile_name: str) -> HttpRefreshResult:
    """Validate an HTTP-only candidate before persisting it; return no secrets."""
    try:
        cached = load_cached_tokens(profile_name=profile_name)
        if cached is None or not cached.cookies:
            raise NotFoundError(
                f"No saved authentication for profile '{profile_name}'",
                hint="Run 'nlm login' for this profile first.",
                resource_type="profile",
            )

        with NotebookLMClient(
            cookies=cached.cookies,
            csrf_token=cached.csrf_token or "",
            session_id=cached.session_id or "",
            build_label=cached.build_label or "",
            base_host=cached.base_host or "",
            profile_name=profile_name,
            is_env_auth=True,
            rpc_transport="http",
        ) as client:
            client._refresh_auth_tokens()
            client.list_notebooks(require_valid_response=True)
            refreshed = AuthTokens(
                cookies=client.cookies,
                csrf_token=client.csrf_token,
                session_id=client._session_id,
                build_label=client._bl,
                base_host=client._base_host,
                extracted_at=time.time(),
            )

        save_tokens_to_cache(
            refreshed,
            profile_name=profile_name,
            expected_revision=cached.revision,
            force=False,
        )
    except ServiceError:
        raise
    except StaleRevisionError as exc:
        raise ConflictError(
            "Profile credentials changed during refresh; retry the command."
        ) from exc
    except Exception as exc:
        raise ServiceError(
            "Could not validate and save the HTTP-only refresh. Check authentication "
            "and connectivity; an expired Google login requires 'nlm login'."
        ) from exc
    return {"profile": profile_name, "status": "success"}
