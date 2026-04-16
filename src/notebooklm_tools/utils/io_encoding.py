"""Normalize stdio text encoding where platform defaults break Unicode (Windows).

Windows consoles often default to cp1252. Typer/Rich then raise UnicodeEncodeError
for characters such as arrows and smart quotes from API text, which terminates
the MCP server on stdio and surfaces as client EOF disconnects.

See: https://github.com/jacob-bd/notebooklm-mcp-cli/issues/156
"""

from __future__ import annotations

import sys


def configure_stdio_utf8_on_windows() -> None:
    """Best-effort UTF-8 for stdout/stderr on Windows (replace unencodable chars)."""
    if sys.platform != "win32":
        return
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError, AttributeError):
            continue
