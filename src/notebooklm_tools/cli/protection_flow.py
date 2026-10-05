"""Shared steps for moving saved logins between plain and protected storage.

Used by `nlm auth storage set` and the `nlm setup` wizard's "Credential
protection" door so both behave identically.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import typer

from notebooklm_tools.cli.utils import make_console

console = make_console()

MODE_LABEL: dict[str | None, str] = {"protected": "protected", "file": "plain", None: "unknown"}
MAC_HINT = (
    "[dim]Usually no popup. If one appears, enter your Mac login password "
    "and click Always Allow.[/dim]"
)


def profile_modes() -> dict[str, str | None]:
    """Storage mode of every real saved profile, sorted by name (None if unreadable)."""
    from notebooklm_tools.services.auth_storage import saved_profile_names
    from notebooklm_tools.utils.config import get_auth_storage_mode

    modes: dict[str, str | None] = {}
    for name in saved_profile_names():
        try:
            modes[name] = get_auth_storage_mode(name)
        except Exception:
            modes[name] = None
    return modes


def pick_profiles_for_mode(
    profiles: list[str], mode: str, modes: dict[str, str | None]
) -> list[str] | None:
    """Checkbox picker of saved profiles; ones already in `mode` are shown but disabled."""
    import questionary  # type: ignore[import-not-found]

    from notebooklm_tools.cli.commands.setup import WIZARD_STYLE

    target_label = "protected" if mode == "protected" else "plain"
    if all(modes.get(p) == mode for p in profiles):
        console.print(f"[green]✓[/green] All saved logins are already {target_label}.")
        return []

    width = max(len(p) for p in profiles)
    choices = [
        questionary.Choice(
            title=f"{p.ljust(width)}   {MODE_LABEL.get(modes.get(p), 'unknown')}",
            value=p,
            disabled=f"already {target_label}" if modes.get(p) == mode else None,
        )
        for p in profiles
    ]
    verb = "protected" if mode == "protected" else "switched back to plain files"
    return cast(
        list[str] | None,
        questionary.checkbox(
            f"Which saved logins should be {verb}?",
            choices=choices,
            instruction="(↑↓ move · Space select · Enter confirm)",
            style=WIZARD_STYLE,
        ).ask(),
    )


def apply_mode(mode: str, targets: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Switch each target profile to `mode`; collect per-profile errors instead of raising."""
    from notebooklm_tools.services import auth_storage
    from notebooklm_tools.services.errors import ServiceError, ValidationError

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for name in targets:
        try:
            results.append(dict(auth_storage.set_storage_mode(mode=mode, profile_name=name)))
        except (ServiceError, ValidationError) as e:
            msg = getattr(e, "user_message", str(e))
            errors.append(msg if len(targets) == 1 else f"{name}: {msg}")
    return results, errors


def offer_plain_backup_cleanup(candidates: list[Path]) -> None:
    """List leftover plain login backups and offer to delete them (default No)."""
    from notebooklm_tools.services.auth_storage import remove_plain_backup_files

    if not candidates:
        return
    n = len(candidates)
    console.print(f"\nFound {n} old plain login backup{'' if n == 1 else 's'}:")
    for c in candidates:
        console.print(f"  - {c}")
    question = "Delete this old plain copy?" if n == 1 else f"Delete these {n} old plain copies?"
    try:
        confirmed = typer.confirm(question, default=False)
    except typer.Abort:  # no keyboard (script / closed stdin): treat as No
        console.print("[dim]Kept them (no answer).[/dim]")
        return
    if confirmed:
        removed = len(remove_plain_backup_files(candidates))
        console.print(f"Removed {removed} old plain {'copy' if removed == 1 else 'copies'}.")


def after_switch(mode: str, results: list[dict[str, Any]]) -> None:
    """Follow-up after switching to protected: Mac popup hint + old plain backup cleanup."""
    if mode != "protected":
        return
    from notebooklm_tools.services.auth_storage import find_plain_backup_files

    if any(r.get("status") != "unchanged" for r in results) and sys.platform == "darwin":
        console.print(MAC_HINT)
    protected_now = [p for p, m in profile_modes().items() if m == "protected"]
    backups = sorted({f for name in protected_now for f in find_plain_backup_files(name)})
    offer_plain_backup_cleanup(backups)
