"""Auth replay diagnostics for NotebookLM credentials."""

from __future__ import annotations

import contextlib
import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class AuthReplayProbe:
    """One auth replay diagnostic lane."""

    name: str
    attempted: bool
    valid: bool
    notebook_count: int | None = None
    detail: str | None = None
    error: str | None = None


@dataclass
class AuthReplayDiagnostic:
    """Diagnostic report comparing normal replay, rotated replay, and CDP."""

    profile: str
    verdict: str
    probes: list[AuthReplayProbe]
    recommendation: str


def diagnose_auth_replay(
    profile: str | None = None,
    *,
    include_cdp: bool = True,
    timeout: float = 15.0,
) -> AuthReplayDiagnostic:
    """Classify whether auth failures are stale cookies or browser-bound replay."""
    if profile is None:
        from notebooklm_tools.utils.config import get_config

        profile = get_config().auth.default_profile

    from notebooklm_tools.core.auth import AuthManager

    manager = AuthManager(profile)
    if not manager.profile_exists():
        return AuthReplayDiagnostic(
            profile=profile,
            verdict="not_configured",
            probes=[],
            recommendation="Run `nlm login` before diagnosing auth replay.",
        )

    try:
        loaded = manager.load_profile()
    except Exception as exc:
        return AuthReplayDiagnostic(
            profile=profile,
            verdict="profile_load_error",
            probes=[
                AuthReplayProbe(
                    name="profile",
                    attempted=True,
                    valid=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            ],
            recommendation="The saved profile could not be loaded. Run `nlm login` again.",
        )

    probes = [
        _probe_saved_httpx_replay(loaded, timeout=timeout),
        _probe_rotated_httpx_replay(manager, loaded, timeout=timeout),
    ]

    if include_cdp:
        probes.append(_probe_cdp_in_page_replay(profile, loaded, timeout=timeout))
    else:
        probes.append(
            AuthReplayProbe(
                name="cdp_in_page",
                attempted=False,
                valid=False,
                detail="Skipped by --no-cdp.",
            )
        )

    return _classify_auth_replay(profile, probes)


def _probe_saved_httpx_replay(profile: Any, *, timeout: float) -> AuthReplayProbe:
    """Run the list-notebooks RPC through httpx without auth recovery."""
    ok, count, error = _direct_list_notebooks_httpx(
        cookies=profile.cookies,
        csrf_token=profile.csrf_token or "",
        session_id=profile.session_id or "",
        build_label=profile.build_label or "",
        timeout=timeout,
    )
    return AuthReplayProbe(
        name="httpx_saved",
        attempted=True,
        valid=ok,
        notebook_count=count,
        error=error,
        detail="Saved cookies/tokens replayed directly through httpx.",
    )


def _probe_rotated_httpx_replay(manager: Any, profile: Any, *, timeout: float) -> AuthReplayProbe:
    """Force RotateCookies, then run the same direct httpx RPC."""
    import httpx as _httpx

    from notebooklm_tools.core.client import NotebookLMClient
    from notebooklm_tools.core.cookie_rotation import rotate_google_cookies

    parser = NotebookLMClient(
        cookies=profile.cookies,
        csrf_token=profile.csrf_token or "diagnostic-no-csrf",
        session_id=profile.session_id or "",
        build_label=profile.build_label or "",
    )
    cookies = parser._get_httpx_cookies()
    parser.close()

    with _httpx.Client(cookies=cookies, timeout=timeout) as client:
        rotation = rotate_google_cookies(
            client,
            storage_path=getattr(manager, "cookies_file", None),
            timeout=timeout,
            force=True,
        )
        if not rotation.success:
            error = rotation.error or rotation.skipped_reason or "RotateCookies did not run"
            return AuthReplayProbe(
                name="httpx_after_rotate",
                attempted=rotation.attempted,
                valid=False,
                error=error,
                detail="RotateCookies failed before the replay probe.",
            )

        ok, count, error = _direct_list_notebooks_httpx_client(
            http_client=client,
            csrf_token=profile.csrf_token or "",
            session_id=profile.session_id or "",
            build_label=profile.build_label or "",
            timeout=timeout,
        )

    return AuthReplayProbe(
        name="httpx_after_rotate",
        attempted=True,
        valid=ok,
        notebook_count=count,
        error=error,
        detail="Forced RotateCookies succeeded, then list_notebooks replayed through httpx.",
    )


def _probe_cdp_in_page_replay(
    profile_name: str, profile: Any, *, timeout: float
) -> AuthReplayProbe:
    """Run the list-notebooks RPC inside a saved browser profile via CDP."""
    from notebooklm_tools.core.client import NotebookLMClient
    from notebooklm_tools.utils import cdp

    if not cdp.has_chrome_profile(profile_name):
        return AuthReplayProbe(
            name="cdp_in_page",
            attempted=False,
            valid=False,
            detail="No saved browser profile is available for CDP.",
        )

    launched = False
    port = cdp.CDP_DEFAULT_PORT + 1
    try:
        debugger_url = cdp.get_debugger_url(port)
        if not debugger_url:
            if not cdp.launch_chrome(port=port, headless=True, profile_name=profile_name):
                return AuthReplayProbe(
                    name="cdp_in_page",
                    attempted=True,
                    valid=False,
                    error="Failed to launch headless browser for CDP probe.",
                )
            launched = True
            debugger_url = cdp.get_debugger_url(port, tries=10)
            if not debugger_url:
                return AuthReplayProbe(
                    name="cdp_in_page",
                    attempted=True,
                    valid=False,
                    error="Headless browser did not expose CDP in time.",
                )

        page = cdp.find_or_create_notebooklm_page(port)
        if not page:
            return AuthReplayProbe(
                name="cdp_in_page",
                attempted=True,
                valid=False,
                error="Could not open a NotebookLM page in the browser profile.",
            )

        ws_url = cdp._normalize_ws_url(page.get("webSocketDebuggerUrl"))
        if not ws_url:
            return AuthReplayProbe(
                name="cdp_in_page",
                attempted=True,
                valid=False,
                error="NotebookLM page did not expose a CDP websocket URL.",
            )

        start = time.time()
        while time.time() - start < timeout:
            if cdp.is_logged_in(cdp.get_current_url(ws_url)):
                break
            time.sleep(0.5)
        else:
            return AuthReplayProbe(
                name="cdp_in_page",
                attempted=True,
                valid=False,
                error="Saved browser profile is not logged in to NotebookLM.",
            )

        html, ready = cdp._wait_for_page_ready(ws_url, timeout=int(timeout))
        if not ready:
            return AuthReplayProbe(
                name="cdp_in_page",
                attempted=True,
                valid=False,
                error="NotebookLM page loaded, but session fields were not found.",
            )

        csrf_token = cdp.extract_csrf_token(html) or profile.csrf_token or ""
        session_id = cdp.extract_session_id(html) or profile.session_id or ""
        build_label = cdp.extract_build_label(html) or profile.build_label or ""

        parser = NotebookLMClient(
            cookies={"diagnostic": "unused"},
            csrf_token=csrf_token or "diagnostic-no-csrf",
            session_id=session_id,
            build_label=build_label,
        )
        body = parser._build_request_body(parser.RPC_LIST_NOTEBOOKS, [None, 1, None, [2]])
        url = parser._build_url(parser.RPC_LIST_NOTEBOOKS)
        parser.close()

        expression = f"""
            (async () => {{
                const response = await fetch({json.dumps(url)}, {{
                    method: "POST",
                    credentials: "include",
                    headers: {{
                        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                        "X-Same-Domain": "1"
                    }},
                    body: {json.dumps(body)}
                }});
                const text = await response.text();
                return JSON.stringify({{status: response.status, url: response.url, text}});
            }})()
        """
        cdp_result = cdp.execute_cdp_command(
            ws_url,
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
        )
        value = cdp_result.get("result", {}).get("value")
        payload = json.loads(value) if isinstance(value, str) else {}
        status = payload.get("status")
        if status != 200:
            return AuthReplayProbe(
                name="cdp_in_page",
                attempted=True,
                valid=False,
                error=f"CDP fetch returned HTTP {status}",
            )

        ok, count, error = _parse_list_notebooks_response(
            payload.get("text", ""),
            csrf_token=csrf_token,
            session_id=session_id,
            build_label=build_label,
        )
        return AuthReplayProbe(
            name="cdp_in_page",
            attempted=True,
            valid=ok,
            notebook_count=count,
            error=error,
            detail="list_notebooks replayed inside the saved browser profile.",
        )
    except Exception as exc:
        return AuthReplayProbe(
            name="cdp_in_page",
            attempted=True,
            valid=False,
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        if launched:
            with contextlib.suppress(Exception):
                cdp.terminate_chrome(port=port)


def _direct_list_notebooks_httpx(
    *,
    cookies: dict[str, str] | list[dict[str, Any]],
    csrf_token: str,
    session_id: str,
    build_label: str,
    timeout: float,
) -> tuple[bool, int | None, str | None]:
    """Run list_notebooks through a fresh httpx client without recovery."""
    import httpx as _httpx

    from notebooklm_tools.core.client import NotebookLMClient

    parser = NotebookLMClient(
        cookies=cookies,
        csrf_token=csrf_token or "diagnostic-no-csrf",
        session_id=session_id,
        build_label=build_label,
    )
    cookie_jar = parser._get_httpx_cookies()
    headers = _diagnostic_rpc_headers(parser)
    parser.close()

    with _httpx.Client(cookies=cookie_jar, headers=headers, timeout=timeout) as client:
        return _direct_list_notebooks_httpx_client(
            http_client=client,
            csrf_token=csrf_token,
            session_id=session_id,
            build_label=build_label,
            timeout=timeout,
        )


def _direct_list_notebooks_httpx_client(
    *,
    http_client: Any,
    csrf_token: str,
    session_id: str,
    build_label: str,
    timeout: float,
) -> tuple[bool, int | None, str | None]:
    """Run list_notebooks through a provided httpx client without recovery."""
    from notebooklm_tools.core.client import NotebookLMClient

    parser = NotebookLMClient(
        cookies={"diagnostic": "unused"},
        csrf_token=csrf_token or "diagnostic-no-csrf",
        session_id=session_id,
        build_label=build_label,
    )
    body = parser._build_request_body(parser.RPC_LIST_NOTEBOOKS, [None, 1, None, [2]])
    url = parser._build_url(parser.RPC_LIST_NOTEBOOKS)
    headers = _diagnostic_rpc_headers(parser)
    try:
        response = http_client.post(url, content=body, headers=headers, timeout=timeout)
        response.raise_for_status()
        return _parse_list_notebooks_response(
            response.text,
            csrf_token=csrf_token,
            session_id=session_id,
            build_label=build_label,
        )
    except Exception as exc:
        return False, None, f"{type(exc).__name__}: {exc}"
    finally:
        parser.close()


def _diagnostic_rpc_headers(parser: Any) -> dict[str, str]:
    """Match the normal NotebookLMClient RPC headers without invoking recovery."""
    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Origin": parser._get_base_url(),
        "Referer": f"{parser._get_base_url()}/",
        "X-Same-Domain": "1",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    if parser.csrf_token:
        headers["X-Goog-Csrf-Token"] = parser.csrf_token
    return headers


def _parse_list_notebooks_response(
    response_text: str,
    *,
    csrf_token: str,
    session_id: str,
    build_label: str,
) -> tuple[bool, int | None, str | None]:
    """Parse a raw list_notebooks batchexecute response."""
    from notebooklm_tools.core.client import NotebookLMClient

    parser = NotebookLMClient(
        cookies={"diagnostic": "unused"},
        csrf_token=csrf_token or "diagnostic-no-csrf",
        session_id=session_id,
        build_label=build_label,
    )
    try:
        parsed = parser._parse_response(response_text)
        result = parser._extract_rpc_result(parsed, parser.RPC_LIST_NOTEBOOKS)
        notebook_list = result[0] if result and isinstance(result[0], list) else result
        count = len(notebook_list) if isinstance(notebook_list, list) else None
        return True, count, None
    except Exception as exc:
        return False, None, f"{type(exc).__name__}: {exc}"
    finally:
        parser.close()


def _classify_auth_replay(profile: str, probes: list[AuthReplayProbe]) -> AuthReplayDiagnostic:
    """Turn probe results into a practical diagnosis."""
    by_name = {probe.name: probe for probe in probes}
    direct = by_name.get("httpx_saved")
    rotated = by_name.get("httpx_after_rotate")
    cdp_probe = by_name.get("cdp_in_page")

    if direct and direct.valid:
        return AuthReplayDiagnostic(
            profile=profile,
            verdict="httpx_ok",
            probes=probes,
            recommendation="No replay problem detected. The saved credentials work through normal httpx.",
        )

    if rotated and rotated.valid:
        return AuthReplayDiagnostic(
            profile=profile,
            verdict="cookie_freshness",
            probes=probes,
            recommendation=(
                "Saved replay failed until RotateCookies ran. Keep RotateCookies in auth recovery; "
                "a full CDP transport is not justified by this result."
            ),
        )

    if cdp_probe and cdp_probe.attempted and cdp_probe.valid:
        return AuthReplayDiagnostic(
            profile=profile,
            verdict="browser_bound_replay",
            probes=probes,
            recommendation=(
                "httpx replay failed but in-browser fetch succeeded. This matches issue #248 "
                "and justifies an opt-in CDP transport for RPC/chat calls."
            ),
        )

    if cdp_probe and not cdp_probe.attempted:
        return AuthReplayDiagnostic(
            profile=profile,
            verdict="httpx_failed_cdp_skipped",
            probes=probes,
            recommendation=(
                "httpx replay failed and CDP was skipped or unavailable. Run `nlm login` to save "
                "a browser profile, then rerun the diagnostic with CDP enabled."
            ),
        )

    return AuthReplayDiagnostic(
        profile=profile,
        verdict="all_failed",
        probes=probes,
        recommendation=(
            "All attempted lanes failed. Re-authenticate with `nlm login`; if it persists, "
            "collect this diagnostic output and the raw error messages."
        ),
    )
