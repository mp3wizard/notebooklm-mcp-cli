"""Experimental browser-backed RPC transport.

This module keeps the CDP implementation small and opt-in. It executes the
same form POSTs that the httpx transport builds, but sends them through
``fetch`` inside the saved NotebookLM browser profile so Chrome supplies the
current browser-bound cookies.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from dataclasses import dataclass

from notebooklm_tools.utils import cdp
from notebooklm_tools.utils.config import get_config

from .errors import ClientAuthenticationError as AuthenticationError

RPC_TRANSPORT_ENV = "NOTEBOOKLM_RPC_TRANSPORT"
RPC_TRANSPORT_CDP = "cdp"
DEFAULT_CDP_READY_TIMEOUT = 30.0


class CdpTransportError(RuntimeError):
    """Raised when the experimental CDP transport cannot complete a request."""


@dataclass(frozen=True)
class CdpPageContext:
    """Browser page metadata needed for in-page RPC fetches."""

    profile_name: str
    port: int
    ws_url: str
    csrf_token: str
    session_id: str
    build_label: str
    launched: bool = False


@dataclass(frozen=True)
class CdpFetchResult:
    """Result returned by an in-page fetch."""

    status_code: int
    text: str
    url: str


def cdp_transport_enabled() -> bool:
    """Return True when the experimental CDP RPC transport is enabled."""
    return os.environ.get(RPC_TRANSPORT_ENV, "").strip().lower() == RPC_TRANSPORT_CDP


def _default_profile_name() -> str:
    try:
        return get_config().auth.default_profile or "default"
    except Exception:
        return "default"


def _find_free_cdp_port() -> int | None:
    for port in cdp.CDP_PORT_RANGE:
        if not cdp.get_debugger_url(port, tries=1, timeout=1):
            return port
    return None


def _wait_for_launched_or_existing_browser(
    *, launch_port: int, profile_name: str, timeout: float
) -> int | None:
    """Wait for our launch, or reuse another profile-owned browser that appears."""
    deadline = time.time() + max(timeout, 1.0)
    while time.time() < deadline:
        if cdp.get_debugger_url(launch_port, tries=1, timeout=1):
            return launch_port

        port, _debugger_url = cdp.find_existing_nlm_chrome(
            profile_name=profile_name,
            include_headless=True,
        )
        if port is not None:
            return port

        time.sleep(0.5)
    return None


def get_cdp_page_context(
    *,
    profile_name: str | None = None,
    timeout: float | None = None,
    csrf_fallback: str = "",
    session_fallback: str = "",
    build_fallback: str = "",
) -> CdpPageContext:
    """Open or reuse a profile-owned NotebookLM page and extract live tokens."""
    profile = profile_name or _default_profile_name()
    wait_timeout = max(float(timeout or DEFAULT_CDP_READY_TIMEOUT), 1.0)

    if not cdp.has_chrome_profile(profile):
        raise AuthenticationError(
            f"CDP transport needs a saved browser profile for '{profile}'. Run `nlm login` first."
        )

    launched = False
    port, _debugger_url = cdp.find_existing_nlm_chrome(
        profile_name=profile,
        include_headless=True,
    )
    if port is None:
        port = _find_free_cdp_port()
        if port is None:
            raise CdpTransportError("No free local CDP port is available for CDP transport.")
        launch_port = port
        if not cdp.launch_chrome(port=port, headless=True, profile_name=profile):
            raise CdpTransportError("Failed to launch headless browser for CDP transport.")
        launched = True
        ready_port = _wait_for_launched_or_existing_browser(
            launch_port=launch_port,
            profile_name=profile,
            timeout=10,
        )
        if ready_port is None:
            with contextlib.suppress(Exception):
                cdp.terminate_chrome(port=launch_port)
            raise CdpTransportError("Headless browser did not expose CDP in time.")
        if ready_port != launch_port:
            with contextlib.suppress(Exception):
                cdp.terminate_chrome(port=launch_port)
            launched = False
            port = ready_port

    try:
        page = cdp.find_or_create_notebooklm_page(port)
        if not page:
            raise CdpTransportError("Could not open a NotebookLM page in the browser profile.")

        ws_url = cdp._normalize_ws_url(page.get("webSocketDebuggerUrl"))
        if not ws_url:
            raise CdpTransportError("NotebookLM page did not expose a CDP websocket URL.")

        deadline = time.time() + wait_timeout
        while time.time() < deadline:
            try:
                if cdp.is_logged_in(cdp.get_current_url(ws_url)):
                    break
            except Exception:  # nosec B110  # transient CDP error during login-poll; retry until timeout
                pass
            time.sleep(0.5)
        else:
            raise AuthenticationError(
                f"Saved browser profile '{profile}' is not logged in to NotebookLM. "
                "Run `nlm login` again."
            )

        html, ready = cdp._wait_for_page_ready(ws_url, timeout=max(1, int(wait_timeout)))
        if not ready:
            raise CdpTransportError("NotebookLM page loaded, but session fields were not found.")

        csrf_token = cdp.extract_csrf_token(html) or csrf_fallback
        session_id = cdp.extract_session_id(html) or session_fallback
        build_label = cdp.extract_build_label(html) or build_fallback
        if not session_id:
            raise CdpTransportError("NotebookLM page did not expose a session ID.")

        return CdpPageContext(
            profile_name=profile,
            port=port,
            ws_url=ws_url,
            csrf_token=csrf_token,
            session_id=session_id,
            build_label=build_label,
            launched=launched,
        )
    except Exception:
        if launched:
            with contextlib.suppress(Exception):
                cdp.terminate_chrome(port=port)
        raise


def fetch_form_in_page(
    ws_url: str,
    url: str,
    body: str,
    *,
    timeout: float | None = None,
    headers: dict[str, str] | None = None,
) -> CdpFetchResult:
    """POST form data through ``fetch`` inside a NotebookLM browser page."""
    request_headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "X-Same-Domain": "1",
    }
    if headers:
        request_headers.update(headers)

    expression = f"""
        (async () => {{
            const response = await fetch({json.dumps(url)}, {{
                method: "POST",
                credentials: "include",
                headers: {json.dumps(request_headers, separators=(",", ":"))},
                body: {json.dumps(body)}
            }});
            const text = await response.text();
            return JSON.stringify({{status: response.status, url: response.url, text}});
        }})()
    """
    response_timeout = max(float(timeout or DEFAULT_CDP_READY_TIMEOUT), 1.0)
    cdp_result = cdp.execute_cdp_command(
        ws_url,
        "Runtime.evaluate",
        {"expression": expression, "awaitPromise": True, "returnByValue": True},
        response_timeout=response_timeout,
    )
    if cdp_result.get("exceptionDetails"):
        raise CdpTransportError(f"CDP Runtime.evaluate failed: {cdp_result['exceptionDetails']}")

    value = cdp_result.get("result", {}).get("value")
    if isinstance(value, str):
        try:
            payload = json.loads(value)
        except json.JSONDecodeError as exc:
            raise CdpTransportError("CDP fetch returned malformed JSON payload.") from exc
    elif isinstance(value, dict):
        payload = value
    else:
        raise CdpTransportError("CDP fetch did not return a value.")

    status = payload.get("status")
    if not isinstance(status, int):
        raise CdpTransportError("CDP fetch returned an invalid HTTP status.")

    return CdpFetchResult(
        status_code=status,
        text=str(payload.get("text", "")),
        url=str(payload.get("url", "")),
    )
