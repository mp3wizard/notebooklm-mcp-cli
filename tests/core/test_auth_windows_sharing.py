"""Windows file-sharing retry behavior for plaintext auth storage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from notebooklm_tools.core import auth


def test_read_json_retries_transient_permission_error(tmp_path, monkeypatch):
    path = tmp_path / "cookies.json"
    path.write_text('{"SID": "ok"}', encoding="utf-8")

    real_read_text = Path.read_text
    attempts = 0

    def flaky_read_text(self, *args, **kwargs):
        nonlocal attempts
        if self == path:
            attempts += 1
            if attempts < 3:
                raise PermissionError("sharing violation")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(auth, "_WINDOWS_SHARE_RETRY_ATTEMPTS", 3)
    monkeypatch.setattr(auth.time, "sleep", lambda _delay: None)
    monkeypatch.setattr(Path, "read_text", flaky_read_text)

    assert auth._read_json_with_windows_retry(path) == {"SID": "ok"}
    assert attempts == 3


def test_read_json_reraises_after_retry_budget(tmp_path, monkeypatch):
    path = tmp_path / "cookies.json"
    path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(auth, "_WINDOWS_SHARE_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(auth.time, "sleep", lambda _delay: None)
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("denied")),
    )

    with pytest.raises(PermissionError, match="denied"):
        auth._read_json_with_windows_retry(path)


def test_atomic_write_retries_transient_replace_failure(tmp_path, monkeypatch):
    target = tmp_path / "auth.json"
    target.write_text('{"old": true}', encoding="utf-8")

    real_replace = auth.os.replace
    attempts = 0

    def flaky_replace(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("sharing violation")
        return real_replace(source, destination)

    monkeypatch.setattr(auth, "_WINDOWS_SHARE_RETRY_ATTEMPTS", 3)
    monkeypatch.setattr(auth.time, "sleep", lambda _delay: None)
    monkeypatch.setattr(auth.os, "replace", flaky_replace)

    auth._atomic_write_json(target, {"new": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"new": True}
    assert attempts == 3
    assert not list(tmp_path.glob("auth.json.tmp.*"))
