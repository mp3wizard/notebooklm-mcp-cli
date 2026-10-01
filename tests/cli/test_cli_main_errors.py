"""Tests for top-level CLI error rendering."""

import pytest

from notebooklm_tools.cli import main
from notebooklm_tools.core.errors import TransientBackendError


def test_cli_main_renders_transient_backend_error_without_traceback(monkeypatch, capsys):
    """Transient backend failures should be a friendly CLI error, not a traceback."""

    def raise_transient_error():
        raise TransientBackendError(
            "Could not reach NotebookLM while verifying the session.",
            hint="Check your connection and retry.",
        )

    monkeypatch.setattr(main, "app", raise_transient_error)
    monkeypatch.setattr("notebooklm_tools.cli.utils.print_update_notification", lambda: None)

    with pytest.raises(SystemExit) as exc_info:
        main.cli_main()

    output = capsys.readouterr().out
    assert exc_info.value.code == 1
    assert "Authentication Error" not in output
    assert "Could not reach NotebookLM" in output
    assert "Check your connection and retry" in output


def _exit_with(code):
    def _app():
        raise SystemExit(code)

    return _app


@pytest.mark.parametrize(
    ("argv", "code", "expected"),
    [
        (["nlm", "notebook", "list"], 0, True),
        (["nlm", "notebook", "list"], 1, False),
        (["nlm", "auth", "storage", "set", "file"], 0, False),
        (["nlm", "login"], 0, False),
        (["nlm", "setup"], 0, False),
    ],
)
def test_cli_main_shows_storage_tip_only_after_successful_command(
    monkeypatch, argv, code, expected
):
    """The real entry point (app() always raises SystemExit) must reach the tip on success."""
    calls = []
    monkeypatch.setattr(main, "app", _exit_with(code))
    monkeypatch.setattr("sys.argv", argv)
    monkeypatch.setattr(
        "notebooklm_tools.cli.utils.print_storage_mode_notification", lambda: calls.append(1)
    )

    with pytest.raises(SystemExit) as exc_info:
        main.cli_main()

    assert exc_info.value.code == code
    assert bool(calls) is expected
