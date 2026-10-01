"""Tests verifying that documented 'nlm auth storage' commands match the real Typer app.

Ensures documentation in:
- docs/AUTHENTICATION.md
- docs/CLI_GUIDE.md
- src/notebooklm_tools/data/references/command_reference.md
cannot drift from the implemented CLI subcommands, arguments, and options.
"""

import re
import shlex
from pathlib import Path

import pytest
import typer

from notebooklm_tools.cli.main import storage_app

# The real command set from storage_app
click_storage = typer.main.get_command(storage_app)
VALID_SUBCOMMANDS = set(click_storage.commands.keys())

# Build mapping of subcommand -> set of valid option strings (e.g. {'--profile', '-p', '--json', ...})
COMMAND_OPTIONS = {}
for name, cmd in click_storage.commands.items():
    opts = set()
    for param in cmd.params:
        if param.opts:
            opts.update(param.opts)
        if param.secondary_opts:
            opts.update(param.secondary_opts)
    COMMAND_OPTIONS[name] = opts

DOC_FILES = [
    Path("docs/AUTHENTICATION.md"),
    Path("docs/CLI_GUIDE.md"),
    Path("src/notebooklm_tools/data/references/command_reference.md"),
]
SRC_FILES = [p for p in Path("src").rglob("*.py")]
ALL_CHECK_FILES = DOC_FILES + SRC_FILES


def extract_documented_storage_commands(file_path: Path) -> list[str]:
    """Extract all 'nlm auth storage ...' command lines or snippets from a file."""
    content = file_path.read_text(encoding="utf-8")
    lines = []
    # Match patterns like:
    # `nlm auth storage status --profile work`
    # nlm auth storage set protected
    # > nlm auth storage set file
    pattern = re.compile(r"nlm\s+auth\s+storage\s+([^\n`\"'\)\\]+)")
    for match in pattern.finditer(content):
        cmd_str = match.group(0).strip()
        # Clean up any trailing punctuation or markdown artifacts
        cmd_str = re.sub(r"[\.,;:>]+$", "", cmd_str).strip()
        lines.append(cmd_str)
    return lines


def test_no_forbidden_or_phantom_storage_commands():
    """Ensure non-existent commands and flags are never documented or used in error text."""
    for file_path in ALL_CHECK_FILES:
        content = file_path.read_text(encoding="utf-8")
        assert "nlm auth storage list" not in content, (
            f"Found phantom 'list' command in {file_path}"
        )
        # Ensure --force is not documented on nlm auth storage
        assert not re.search(r"nlm\s+auth\s+storage\s+.*--force\b", content), (
            f"Found phantom '--force' flag in {file_path}"
        )
        # Ensure --format is not documented on nlm auth storage
        assert not re.search(r"nlm\s+auth\s+storage\s+.*--format\b", content), (
            f"Found phantom '--format' flag in {file_path}"
        )
        # Ensure --verify is not documented on nlm auth storage
        assert not re.search(r"nlm\s+auth\s+storage\s+.*--verify\b", content), (
            f"Found phantom '--verify' flag in {file_path}"
        )


@pytest.mark.parametrize("file_path", ALL_CHECK_FILES)
def test_documented_storage_commands_exist(file_path: Path):
    """Verify all documented or emitted 'nlm auth storage ...' lines use real subcommands and flags."""
    commands = extract_documented_storage_commands(file_path)
    if file_path in DOC_FILES:
        assert len(commands) > 0, f"No nlm auth storage commands found in {file_path}"

    for cmd_line in commands:
        # Strip '[OPTIONS]', angle-bracket placeholders, rich tags, and f-string tokens
        cleaned = re.sub(r"\[OPTIONS\]", "", cmd_line, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"\[/?[a-z_]+\]", "", cleaned
        )  # rich console markup tags like [cyan] or [/cyan]
        cleaned = re.sub(r"\{[^\}]+\}", "default", cleaned)  # f-string substitutions like {profile}
        # Normalize placeholders like <mode>, <name>, [choice], [file|protected] to valid dummy tokens
        cleaned = re.sub(r"<mode>|\[file\|protected\]", "protected", cleaned)
        cleaned = re.sub(r"<name>|<profile>|<old_clean>", "default", cleaned)
        cleaned = re.sub(r"\[choice\]", "file", cleaned)

        tokens = shlex.split(cleaned)
        # Expected format: ['nlm', 'auth', 'storage', <subcmd>, ...]
        assert tokens[:3] == ["nlm", "auth", "storage"], f"Malformed command prefix in: {cmd_line}"
        if len(tokens) == 3:
            # Bare 'nlm auth storage' (e.g. in descriptions)
            continue

        subcmd = tokens[3]
        assert subcmd in VALID_SUBCOMMANDS, (
            f"Documented subcommand '{subcmd}' in {file_path} does not exist in storage_app! "
            f"Valid subcommands are: {VALID_SUBCOMMANDS}"
        )

        valid_opts = COMMAND_OPTIONS[subcmd]
        # Check every flag token starting with '-'
        for token in tokens[4:]:
            if token.startswith("-"):
                assert token in valid_opts, (
                    f"Documented flag '{token}' in '{cmd_line}' ({file_path}) is not recognized "
                    f"by subcommand '{subcmd}'. Valid flags are: {valid_opts}"
                )
