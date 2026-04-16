"""Windows stdio UTF-8 bootstrap (Issue #156)."""

import sys
from unittest.mock import MagicMock


def test_configure_stdio_noop_on_non_windows(monkeypatch):
    from notebooklm_tools.utils.io_encoding import configure_stdio_utf8_on_windows

    monkeypatch.setattr(sys, "platform", "linux")
    fake = MagicMock()
    monkeypatch.setattr(sys, "stdout", fake)
    configure_stdio_utf8_on_windows()
    fake.reconfigure.assert_not_called()


def test_configure_stdio_calls_reconfigure_on_windows(monkeypatch):
    from notebooklm_tools.utils.io_encoding import configure_stdio_utf8_on_windows

    monkeypatch.setattr(sys, "platform", "win32")
    out = MagicMock()
    err = MagicMock()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)

    configure_stdio_utf8_on_windows()

    out.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
    err.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")


def test_cp1252_crashes_on_unicode_arrow():
    """Prove the root cause: cp1252 cannot encode characters like → (U+2192)."""
    import io

    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    with __import__("pytest").raises(UnicodeEncodeError):
        stream.write("\u2192")


def test_reconfigure_utf8_fixes_cp1252_unicode_crash():
    """Prove the fix: reconfiguring cp1252 stream to UTF-8 prevents the crash."""
    import io

    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    stream.reconfigure(encoding="utf-8", errors="replace")
    stream.write("\u2192 arrow and \u201csmart quotes\u201d")
    stream.flush()
    stream.seek(0)
    assert "\u2192" in stream.read()
