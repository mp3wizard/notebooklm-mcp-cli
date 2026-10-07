"""CDP port selection should survive reserved conventional port ranges."""

from __future__ import annotations

import socket

import pytest

from notebooklm_tools.utils import cdp


class _FakeSocket:
    def __init__(self, binds: list[int], *, ephemeral_port: int = 54321) -> None:
        self.binds = binds
        self.ephemeral_port = ephemeral_port
        self.bound_port: int | None = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def bind(self, address: tuple[str, int]) -> None:
        port = address[1]
        self.binds.append(port)
        self.bound_port = port
        if port != 0:
            raise PermissionError(13, "reserved")

    def getsockname(self) -> tuple[str, int]:
        assert self.bound_port == 0
        return ("127.0.0.1", self.ephemeral_port)

    def close(self) -> None:
        pass


def test_find_available_port_falls_back_to_os_assigned_port(monkeypatch):
    binds: list[int] = []

    monkeypatch.setattr(
        socket,
        "socket",
        lambda *_args, **_kwargs: _FakeSocket(binds, ephemeral_port=54321),
    )

    assert cdp.find_available_port(starting_from=9222, max_attempts=3) == 54321
    assert binds == [9222, 9223, 9224, 0]


def test_find_available_port_can_require_exact_range(monkeypatch):
    binds: list[int] = []

    monkeypatch.setattr(
        socket,
        "socket",
        lambda *_args, **_kwargs: _FakeSocket(binds),
    )

    with pytest.raises(RuntimeError, match="No available ports"):
        cdp.find_available_port(
            starting_from=9223,
            max_attempts=1,
            allow_ephemeral_fallback=False,
        )

    assert binds == [9223]


def test_interactive_login_launches_browser_on_ephemeral_fallback(monkeypatch):
    """The interactive CDP login path must use the fallback port it discovers."""
    binds: list[int] = []
    launched: list[int] = []

    class _RunningProcess:
        stderr = None

        def poll(self):
            return None

    monkeypatch.setattr(
        socket,
        "socket",
        lambda *_args, **_kwargs: _FakeSocket(binds, ephemeral_port=54321),
    )
    monkeypatch.setattr(cdp, "_kill_stale_nlm_browsers", lambda: None)
    monkeypatch.setattr(cdp, "find_existing_nlm_chrome", lambda **_kwargs: (None, None))
    monkeypatch.setattr(cdp, "get_chrome_path", lambda: "/fake/chrome")
    monkeypatch.setattr(
        cdp,
        "_get_profile_dir_for_launch",
        lambda *_args, **_kwargs: "/fake/profile",
    )
    monkeypatch.setattr(cdp, "is_profile_locked", lambda *_args, **_kwargs: False)

    def fake_launch(port, profile_name="default"):
        launched.append(port)
        cdp._chrome_process = _RunningProcess()
        cdp._chrome_port = port
        return True

    monkeypatch.setattr(cdp, "launch_chrome", fake_launch)
    monkeypatch.setattr(
        cdp,
        "get_debugger_url",
        lambda port, **_kwargs: f"ws://127.0.0.1:{port}/devtools/browser/test",
    )
    monkeypatch.setattr(
        cdp,
        "extract_cookies_from_page",
        lambda base_url, *_args, **_kwargs: {
            "cookies": {"SID": "ok"},
            "base_url": base_url,
        },
    )

    try:
        result = cdp.extract_cookies_via_cdp(profile_name="default")
    finally:
        cdp._chrome_process = None
        cdp._chrome_port = None

    assert launched == [54321]
    assert binds == [*range(9222, 9232), 0]
    assert result["base_url"] == "http://127.0.0.1:54321"
    assert result["reused_existing"] is False
