"""Tests for WSL networking utilities."""

import subprocess
from unittest.mock import Mock, call

from notebooklm_tools.utils import wsl


def _result(args: list[str], stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, returncode=0, stdout=stdout, stderr="")


def test_get_windows_host_ip_uses_loopback_in_mirrored_mode(monkeypatch):
    monkeypatch.setattr(wsl, "is_wsl", lambda: True)
    run = Mock(return_value=_result(["wslinfo", "--networking-mode"], "mirrored\n"))
    monkeypatch.setattr(wsl.subprocess, "run", run)

    assert wsl.get_windows_host_ip() == "127.0.0.1"
    run.assert_called_once_with(
        ["wslinfo", "--networking-mode"],
        capture_output=True,
        text=True,
        errors="replace",
        check=True,
        timeout=5,
    )


def test_get_windows_host_ip_uses_gateway_in_nat_mode(monkeypatch):
    monkeypatch.setattr(wsl, "is_wsl", lambda: True)
    run = Mock(
        side_effect=[
            _result(["wslinfo", "--networking-mode"], "nat\n"),
            _result(["ip", "route"], "default via 172.20.112.1 dev eth0\n"),
        ]
    )
    monkeypatch.setattr(wsl.subprocess, "run", run)

    assert wsl.get_windows_host_ip() == "172.20.112.1"
    assert run.call_args_list == [
        call(
            ["wslinfo", "--networking-mode"],
            capture_output=True,
            text=True,
            errors="replace",
            check=True,
            timeout=5,
        ),
        call(
            ["ip", "route"],
            capture_output=True,
            text=True,
            errors="replace",
            check=True,
        ),
    ]


def test_get_windows_host_ip_uses_gateway_when_wslinfo_is_unavailable(monkeypatch):
    monkeypatch.setattr(wsl, "is_wsl", lambda: True)

    def run(args, **kwargs):
        if args[0] == "wslinfo":
            raise FileNotFoundError
        return _result(args, "default via 172.20.112.1 dev eth0\n")

    monkeypatch.setattr(wsl.subprocess, "run", run)

    assert wsl.get_windows_host_ip() == "172.20.112.1"


def test_launch_windows_chrome_preserves_non_ascii_windows_temp_path(monkeypatch):
    monkeypatch.setattr(wsl, "is_wsl", lambda: True)
    monkeypatch.setattr(
        wsl,
        "find_windows_chrome",
        lambda: r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )

    calls = []
    powershell_call = None

    def run(args, **kwargs):
        nonlocal powershell_call
        calls.append((args, kwargs))
        if args[0] == "powershell.exe":
            powershell_call = (args, kwargs)
            return _result(args, "C:\\Users\\王小明\\AppData\\Local\\Temp\\")
        if args[0] == "wslpath" and args[1] == "-u":
            return _result(args, "/tmp/nlm-chrome")
        return _result(args, "")

    class FakeProcess:
        pid = 4242

    popen_args = []
    monkeypatch.setattr(wsl.subprocess, "run", run)
    monkeypatch.setattr(
        wsl.subprocess, "Popen", lambda args, **_: popen_args.append(args) or FakeProcess()
    )

    process = wsl.launch_windows_chrome()

    assert process.pid == 4242
    assert powershell_call is not None
    powershell_args, powershell_kwargs = powershell_call
    assert powershell_kwargs["encoding"] == "utf-8"
    assert powershell_kwargs["errors"] == "strict"
    assert "OutputEncoding" in powershell_args[-1]
    assert any(
        arg.startswith("--user-data-dir=C:\\Users\\王小明\\AppData\\Local\\Temp")
        and "nlm-chrome-" in arg
        for arg in popen_args[0]
    )
