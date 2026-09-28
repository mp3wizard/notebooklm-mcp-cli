# Guided `nlm setup` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make bare `nlm setup` a safe interactive Add, Remove, and JSON wizard for supported MCP clients and optional NLM skills.

**Architecture:** Keep `setup.py` and `skill.py` as the existing client adapters. Add a small config-safety module and a separate wizard module, then improve the Codex and GitHub Copilot adapters to use current client behavior. The wizard calls adapters, records a result for each target, and never calls NotebookLM APIs.

**Tech Stack:** Python 3.11+, Typer, Rich, questionary, tomlkit, pytest, uv.

**Spec:** `docs/superpowers/specs/2026-09-27-setup-wizard-design.md` (commit `5ba4d20`). Read it before editing code.

## Global Constraints

- Work only in the isolated `codex/setup-wizard-design` worktree until Jacob's unpublished main-checkout fixes are ready to integrate. Do not reset, overwrite, or stage those fixes.
- Bare `nlm setup` is offline: no NotebookLM authentication, API calls, or server startup.
- Preserve the syntax and established behavior of existing direct setup and skill commands; add explicit options where a new scope is needed.
- Default MCP setup to the user/app level. Default optional skill installation to **All projects (user level)**; offer **This folder (project level)**.
- Codex CLI and the ChatGPT desktop app share one local MCP target and one `agents` skill destination. Exclude Alef from the wizard.
- Before mutating any existing config or skill folder, create a private backup under `~/.notebooklm-mcp-cli/backups/`. If backup or parsing fails, leave that target untouched.
- Use an absolute `notebooklm-mcp` path and `tool_timeout_sec = 300` for new/repaired Codex entries. Do not silently replace existing entries.
- Remove only recognized NLM entries and exact installed NLM skill folders; preserve unrelated configuration.
- If code changes require a local uv-tool reinstall, run `uv cache clean && uv tool install --force .` in that order.
- Do not add any Co-Authored/Co-developed-with-Codex commit trailers.

## Review Focus

- A config path is a symlink: refuse a direct replacement and explain the path; never replace the link itself. Test in Task 1.
- `CODEX_HOME` is custom: show and use the resolved CLI config path; do not imply the desktop app shares it unless that is known. Test in Task 2.
- A legacy NLM MCP name coexists with unrelated MCP servers: remove only recognized NLM entries and do not create a duplicate. Test in Task 2.
- A VS Code profile cannot be identified: skip global Copilot setup rather than writing `.vscode/mcp.json` in an accidental working directory. Test in Task 3.
- An installed skill is newer than the package or contains extra personal files: do not downgrade it, and back up the full folder before any approved replacement. Test in Task 4.

---

### Task 1: Safe local config and backup primitives

**Files:**
- Create: `src/notebooklm_tools/cli/setup_safety.py`
- Modify: `src/notebooklm_tools/cli/commands/setup.py` (`_read_json_config`, `_write_json_config`)
- Test: `tests/cli/test_setup_safety.py`

**Interfaces:**
- Produces `ConfigParseError`, `read_json_config(path: Path) -> dict`, `backup_existing(path: Path, *, label: str) -> Path | None`, `atomic_write_text(path: Path, content: str) -> None`, and `capture_backups() -> Iterator[list[Path]]`. `capture_backups` uses a `ContextVar`; while active, each successful `backup_existing` appends its path to the list. The wizard uses that list for its per-target summary without changing existing Boolean adapter APIs.
- `setup.py` keeps its existing private `_read_json_config` and `_write_json_config` names as wrappers so callers and current tests remain compatible. `_write_json_config` returns the backup path for summaries; existing callers may ignore it.
- `backup_existing` handles a file or directory. It uses a unique timestamp plus random suffix under `~/.notebooklm-mcp-cli/backups/`, owner-only directory/file permissions, and retains the source's owner execute bit for backed-up scripts.

- [ ] **Step 1: Write failing tests** for missing versus malformed JSON, backup failure, symlink refusal, directory backup, atomic replacement, and permissions. Use `tmp_path` and patch `Path.home` so tests cannot touch real user config.

```python
def test_malformed_json_is_not_replaced(tmp_path):
    path = tmp_path / "mcp.json"
    original = '{"servers": {,}'
    path.write_text(original)
    with pytest.raises(ConfigParseError):
        read_json_config(path)
    assert path.read_text() == original

def test_atomic_write_rejects_symlink(tmp_path):
    target = tmp_path / "real.json"
    target.write_text('{"keep": true}')
    link = tmp_path / "mcp.json"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symbolic link"):
        atomic_write_text(link, '{"keep": false}')
    assert target.read_text() == '{"keep": true}'
```

- [ ] **Step 2: Run** `uv run pytest tests/cli/test_setup_safety.py -v`. Confirm both tests fail because the new helpers do not exist.
- [ ] **Step 3: Implement** the helpers. Import `json`, `os`, `shutil`, `stat`, `tempfile`, `uuid`, `contextmanager`, `ContextVar`, `datetime`, `timezone`, `Path`, and `Iterator` in the new module. Missing JSON returns `{}`; malformed or non-object JSON raises `ConfigParseError`. For an existing path, back up before write. Use `tempfile.mkstemp(dir=path.parent)`, close the descriptor, preserve original mode, validate serialized JSON, then `os.replace`; unlink the temporary file in `finally` on failure. Reject symlink destinations. Never print backup contents.

```python
class ConfigParseError(ValueError):
    def __init__(self, path: Path, cause: Exception):
        super().__init__(f"Cannot parse {path}: {cause}")
        self.path = path

_backup_log: ContextVar[list[Path] | None] = ContextVar("nlm_setup_backups", default=None)

def read_json_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigParseError(path, exc) from exc
    if not isinstance(value, dict):
        raise ConfigParseError(path, ValueError("expected a JSON object"))
    return value

def _write_json_config(path: Path, config: dict) -> Path | None:
    backup = backup_existing(path, label="mcp-config")
    rendered = json.dumps(config, indent=2) + "\n"
    json.loads(rendered)
    atomic_write_text(path, rendered)
    return backup

def backup_existing(path: Path, *, label: str) -> Path | None:
    if path.is_symlink():
        raise ValueError(f"Refusing symbolic link: {path}")
    if not path.exists():
        return None
    root = Path.home() / ".notebooklm-mcp-cli" / "backups"
    if root.is_symlink():
        raise ValueError(f"Refusing symbolic-link backup root: {root}")
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    root.chmod(0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = root / f"{stamp}-{uuid.uuid4().hex[:8]}-{label}"
    try:
        if path.is_dir():
            shutil.copytree(path, backup_path, symlinks=True)
            descendants = [backup_path, *backup_path.rglob("*")]
        else:
            shutil.copy2(path, backup_path)
            descendants = [backup_path]
        for item in descendants:
            if item.is_symlink():
                continue
            mode = 0o700 if item.is_dir() or item.stat().st_mode & stat.S_IXUSR else 0o600
            item.chmod(mode)
    except Exception:
        if backup_path.is_dir():
            shutil.rmtree(backup_path)
        else:
            backup_path.unlink(missing_ok=True)
        raise
    recorded = _backup_log.get()
    if recorded is not None:
        recorded.append(backup_path)
    return backup_path

def atomic_write_text(path: Path, content: str) -> None:
    if path.is_symlink():
        raise ValueError(f"Refusing symbolic link: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

@contextmanager
def capture_backups() -> Iterator[list[Path]]:
    recorded: list[Path] = []
    token = _backup_log.set(recorded)
    try:
        yield recorded
    finally:
        _backup_log.reset(token)
```

- [ ] **Step 4: Run** `uv run pytest tests/cli/test_setup_safety.py tests/cli/test_setup_github_copilot.py tests/cli/test_setup_opencode.py -v`. Confirm all pass and malformed files remain unchanged.
- [ ] **Step 5: Commit** only the safety helper, adapter wrappers, and tests: `git commit -m "fix(setup): preserve configs on parse and write failures"`.

### Task 2: One safe Codex and ChatGPT desktop target

**Files:**
- Modify: `src/notebooklm_tools/cli/commands/setup.py` (`_codex_config_path`, `_detect_tool`, `_setup_codex`, `_remove_single`, client aliases)
- Modify: `pyproject.toml`, `uv.lock` (add `tomlkit>=0.15,<1`)
- Test: `tests/cli/test_setup_codex_desktop.py`

**Interfaces:**
- Produces `_detect_chatgpt_desktop() -> bool`, `_codex_config_path() -> Path`, `_codex_repair_reason() -> str | None`, `_edit_codex_entry(path: Path, *, command: str | None, remove: bool = False) -> Path | None`, and `chatgpt-desktop` as an alias for `codex` in direct add/remove commands. `_setup_codex(repair: bool = False)` preserves the direct command's current no-replace behavior; the wizard passes `repair=True` only after showing the reason and receiving approval.
- `_codex_config_path` honors a nonempty `CODEX_HOME`; without it, use `~/.codex`. Show the resolved path in output. If `CODEX_HOME` differs from the desktop app's default location, explain that desktop availability is not established by the CLI write.
- `_edit_codex_entry` parses with `tomlkit`, changes only recognized NLM tables, sets `command`, empty `args`, and `tool_timeout_sec = 300` for Add, and removes only recognized NLM tables for Remove. It calls Task 1's backup and atomic writer.

- [ ] **Step 1: Write failing tests** for macOS, Windows, and Linux desktop detection; desktop-only add/remove; CLI add with an absolute executable; timeout; approved repair of an existing bare-path/short-timeout entry; comment-preserving TOML; malformed TOML fail-closed; custom `CODEX_HOME`; and legacy name removal. Patch platform, environment, subprocess, home, and `shutil.which` rather than changing real Codex settings.

```python
def test_codex_cli_add_uses_absolute_server_path(monkeypatch, tmp_path):
    from types import SimpleNamespace
    calls = []
    monkeypatch.setattr(setup.shutil, "which", lambda name: {
        "codex": "/usr/local/bin/codex",
        "notebooklm-mcp": "/home/user/.local/bin/notebooklm-mcp",
    }.get(name))
    monkeypatch.setattr(setup.subprocess, "run", lambda args, **kw: calls.append(args) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(setup, "_codex_config_path", lambda: tmp_path / ".codex")
    assert setup._setup_codex() is True
    assert calls[0][-1] == "/home/user/.local/bin/notebooklm-mcp"
    assert tomlkit.parse((tmp_path / ".codex" / "config.toml").read_text())["mcp_servers"][setup.MCP_SERVER_NAME]["tool_timeout_sec"] == 300
```

- [ ] **Step 2: Run** `uv run pytest tests/cli/test_setup_codex_desktop.py -v`; confirm the new cases fail against the current bare-command/append behavior.
- [ ] **Step 3: Add tomlkit** to `pyproject.toml`, update `uv.lock` with `uv lock`, then implement a TOML edit that preserves comments and unrelated tables. Convert `tomlkit` parse failures to `ConfigParseError` before any mutation. Use Task 1's backup before CLI-managed mutation. Pass the resolved absolute server path into `codex mcp add`. After CLI add, set the timeout; if this second step fails, report a partial failure with the backup path rather than claiming success. If the CLI is absent but the desktop app is detected, edit `config.toml` directly. Reuse the TOML editor for desktop-only removal. Detect an existing bad path or timeout below 300 and expose it through `_codex_repair_reason`; repair only when explicitly requested.

```python
doc = tomlkit.parse(path.read_text(encoding="utf-8") if path.exists() else "")
if "mcp_servers" not in doc:
    doc["mcp_servers"] = tomlkit.table()
servers = doc["mcp_servers"]
entry = servers.get(MCP_SERVER_NAME) or tomlkit.table()
assert command is not None
entry["command"] = command
entry["args"] = []
entry["tool_timeout_sec"] = 300
servers[MCP_SERVER_NAME] = entry
atomic_write_text(path, tomlkit.dumps(doc))
```

- [ ] **Step 4: Run** `uv run pytest tests/cli/test_setup_codex_desktop.py tests/cli/test_mcp_branding.py -v`. Confirm direct `nlm setup add codex` and `nlm setup add chatgpt-desktop` use the same target.
- [ ] **Step 5: Commit** Codex adapter, dependencies, lockfile, and tests: `git commit -m "feat(setup): support shared Codex desktop configuration"`.

### Task 3: GitHub Copilot user-profile setup without project surprises

**Files:**
- Modify: `src/notebooklm_tools/cli/commands/setup.py` (`_github_copilot_config_path`, `_setup_github_copilot`, `_remove_single`, `setup_add`, `setup_remove`)
- Test: `tests/cli/test_setup_github_copilot.py`

**Interfaces:**
- Produces `_github_copilot_config_path(scope: str = "project") -> Path | None` and `_is_copilot_configured(scope: str) -> bool`. `project` preserves `.vscode/mcp.json`; `user` resolves the VS Code default user profile's `mcp.json` for the OS. `_setup_github_copilot(scope: str = "project")` and `_remove_single(client: str, profile: str | None = None, scope: str = "project")` use that resolver. The wizard passes `scope="user"`; existing direct commands keep their project default and gain `--scope user`. Update direct `nlm setup remove all` to include a configured user-level Copilot entry as a separately identified target under its existing confirmation.
- In user scope, prefer `code --add-mcp` with a JSON argument containing `name`, absolute `command`, and `args`. Locate and back up the user-profile config before invoking it. If the profile path is ambiguous or a custom profile cannot be resolved, return a skip with the path/VS Code UI instruction. Direct strict-JSON writes use Task 1's safe writer. If a file contains JSONC comments/trailing commas and cannot be edited while preserving them, refuse mutation and report the file.

- [ ] **Step 1: Write failing tests** for macOS/Windows/Linux user-profile paths, user-scope CLI add, user-scope status detection, existing project-scope direct behavior, unknown profile safe skip, JSONC safe skip on removal, direct `remove all` finding user-level Copilot, and an unrelated `servers` entry surviving removal.

```python
def test_unknown_copilot_profile_does_not_write_project_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(setup, "_github_copilot_config_path", lambda scope="project": None if scope == "user" else tmp_path / ".vscode" / "mcp.json")
    assert setup._setup_github_copilot(scope="user") is False
    assert not (tmp_path / ".vscode" / "mcp.json").exists()
```

- [ ] **Step 2: Run** `uv run pytest tests/cli/test_setup_github_copilot.py -v`; confirm the new scope cases fail.
- [ ] **Step 3: Implement** explicit scope routing. Reject `--scope` for clients other than GitHub Copilot. For user scope, resolve the default VS Code profile path, back it up, and call `code --add-mcp` with the absolute server path when possible. When the resulting file is strict JSON, re-read and verify the recognized entry. If VS Code returns success but its file uses JSONC, rely on the client command's result and report that local verification was limited; do not rewrite the file. On removal, edit only the recognized `servers` key; if the file is JSONC and cannot be round-tripped safely, print the exact file and skip. Keep project direct setup behavior and fail closed on malformed project JSON.

```python
absolute_server_path = _find_mcp_server_path()
if absolute_server_path is None:
    console.print("[red]notebooklm-mcp is not installed in PATH[/red]")
    return False
payload = json.dumps({"name": MCP_SERVER_NAME, "command": absolute_server_path, "args": []})
result = subprocess.run([code_cmd, "--add-mcp", payload], capture_output=True, text=True, timeout=15)
if result.returncode != 0:
    console.print(f"[red]VS Code rejected MCP setup:[/red] {result.stderr.strip()}")
    return False
```

- [ ] **Step 4: Run** `uv run pytest tests/cli/test_setup_github_copilot.py tests/cli/test_setup_safety.py -v` and verify both scopes and safety cases pass.
- [ ] **Step 5: Commit** adapter and tests: `git commit -m "feat(setup): add global GitHub Copilot scope"`.

### Task 4: Safe skill installation, upgrade, and removal

**Files:**
- Modify: `src/notebooklm_tools/cli/commands/skill.py`
- Modify: `pyproject.toml`, `uv.lock` (add direct `packaging>=24,<27` for version comparison)
- Test: `tests/cli/test_skill_install.py`
- Test: `tests/cli/test_setup_skill_actions.py`

**Interfaces:**
- Produces `SkillActionResult(status: str, path: Path, backup_path: Path | None, message: str)` and `skill_action(tool: str, level: str, action: Literal["install", "remove"], *, confirm_replace: Callable[[str], bool]) -> SkillActionResult`. Status is `installed`, `updated`, `current`, `newer`, `removed`, `skipped`, or `failed`.
- Reuse `TOOL_CONFIGS`, `check_install_status`, `_get_installed_version`, `install_skill_md`, and the existing uninstall logic. Do not invoke the Typer command functions from the wizard; extract an internal operation so the wizard owns the confirmation prompts.
- Map `codex`, `chatgpt-desktop`, and `gemini-cli` to the single `agents` directory for a given level. Map Claude Desktop to no local skill target unless Claude Code is independently detected. Detect the other existing `TOOL_CONFIGS` targets normally, including skill-only OpenClaw and Hermes when installed. Exclude `alef-agent` and `other` from wizard choices.

- [ ] **Step 1: Write failing tests** for user versus project destination, shared `agents` deduplication, skill-only OpenClaw/Hermes choices when detected, current/newer version skip, older/unversioned confirmation, full-directory backup before replacement or deletion, backup failure, and Claude Desktop-only omission.

```python
def test_newer_skill_is_never_downgraded(monkeypatch, tmp_path):
    skill_dir = tmp_path / "nlm-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text('---\nversion: "99.0.0"\n---\n')
    monkeypatch.setitem(skill.TOOL_CONFIGS, "agents", {"user": skill_dir, "format": "skill.md"})
    assert skill_action("agents", "user", "install", confirm_replace=lambda _: True).status == "newer"
    assert '99.0.0' in (skill_dir / "SKILL.md").read_text()
```

- [ ] **Step 2: Run** `uv run pytest tests/cli/test_setup_skill_actions.py tests/cli/test_skill_install.py -v`; confirm new cases fail.
- [ ] **Step 3: Implement** one internal skill operation, importing `dataclass`, `Version`, and `InvalidVersion`, and using Task 1's `backup_existing` for every replacement and removal. Add `packaging>=24,<27` as a direct dependency, run `uv lock`, and compare versions with `packaging.version.Version`; treat an unparsable version as unversioned and require confirmation. Keep the existing `nlm skill install/uninstall/update` prompts and output stable by routing them through the internal helper or leaving their wrappers with equivalent behavior. Do not delete a directory when backup fails.

```python
@dataclass(frozen=True)
class SkillActionResult:
    status: str
    path: Path
    backup_path: Path | None
    message: str

installed, path = check_install_status(tool, level)
assert path is not None
if action == "remove":
    if not installed:
        return SkillActionResult("skipped", path, None, "Skill is not installed")
    if not confirm_replace(f"Remove skill at {path}?"):
        return SkillActionResult("skipped", path, None, "Removal declined")
    backup = None
    try:
        backup = backup_existing(path, label=f"skill-{tool}-{level}")
        shutil.rmtree(path)
    except (OSError, ValueError) as exc:
        return SkillActionResult("failed", path, backup, f"Removal failed: {exc}")
    return SkillActionResult("removed", path, backup, "Removed")
current_version = _get_installed_version(tool, level) if installed else None
try:
    comparison = Version(current_version) if current_version else None
except InvalidVersion:
    comparison = None
if installed and comparison == Version(__version__):
    return SkillActionResult("current", path, None, "Already current")
if installed and comparison is not None and comparison > Version(__version__):
    return SkillActionResult("newer", path, None, "Newer skill preserved")
if installed and not confirm_replace(f"Replace skill at {path}?"):
    return SkillActionResult("skipped", path, None, "Replacement declined")
try:
    backup = backup_existing(path, label=f"skill-{tool}-{level}") if installed else None
except (OSError, ValueError) as exc:
    return SkillActionResult("failed", path, None, f"Backup failed: {exc}")
```

- [ ] **Step 4: Run** `uv run pytest tests/cli/test_setup_skill_actions.py tests/cli/test_skill_install.py -v`; confirm no regression in direct skill commands.
- [ ] **Step 5: Commit** skill operations, dependency if needed, lockfile, and tests: `git commit -m "feat(skill): back up and version-check setup actions"`.

### Task 5: Add and JSON wizard flows

**Files:**
- Create: `src/notebooklm_tools/cli/commands/setup_wizard.py`
- Modify: `src/notebooklm_tools/cli/commands/setup.py` (Typer callback and shared target wrappers)
- Modify: `pyproject.toml`, `uv.lock` (add `questionary>=2.1,<3`)
- Modify: `docs/CLI_GUIDE.md` and `src/notebooklm_tools/cli/ai_docs.py` (new guided entry point and scopes)
- Test: `tests/cli/test_setup_wizard.py`

**Interfaces:**
- Produces `run_setup_wizard() -> int`, `scan_mcp_targets() -> list[SetupTarget]`, `add_one_mcp(client: str, *, repair: bool = False) -> bool`, `run_add(selected: list[str]) -> list[SetupResult]`, and `copy_to_clipboard(value: str) -> bool`.
- `SetupTarget` carries `id`, `label`, `installed`, `configured`, `destination`, `skill_id`, and optional `repair_reason`. `SetupResult` carries `id`, `status`, `destination`, `backup_paths`, and `message`. Keep these in `setup_wizard.py` and use adapter functions from Tasks 1–4. Wrap each adapter call in Task 1's `capture_backups`; copy its recorded paths into the result.
- The setup Typer app sets `no_args_is_help=False`; its `@app.callback(invoke_without_command=True)` calls `run_setup_wizard` only when no subcommand was supplied. Check `sys.stdin.isatty()` before any questionary prompt; noninteractive exit is 1. A user cancellation exits 130 with a partial-result summary.

- [ ] **Step 1: Write failing tests** for bare setup versus `--help` and existing subcommands, non-TTY status 1, checkbox multi-select and Select all, questionary returning `None` on cancellation, one failed tool not blocking others, Codex/ChatGPT single target, global Copilot routing, global-default skill choice, JSON generator reuse, and clipboard success/fallback across macOS, Windows, and Linux.

```python
def test_bare_setup_noninteractive_exits_without_changes(monkeypatch):
    monkeypatch.setattr(setup_wizard, "is_interactive", lambda: False)
    result = CliRunner().invoke(main.app, ["setup"])
    assert result.exit_code == 1
    assert "interactive terminal" in result.output.lower()

def test_add_continues_after_one_failure(monkeypatch):
    monkeypatch.setattr(setup_wizard, "scan_mcp_targets", lambda: [
        setup_wizard.SetupTarget("cursor", "Cursor", True, False, None, "cursor"),
        setup_wizard.SetupTarget("codex", "Codex / ChatGPT", True, False, None, "agents"),
    ])
    monkeypatch.setattr(setup_wizard, "add_one_mcp", lambda client, **kw: client != "cursor")
    results = setup_wizard.run_add(["cursor", "codex"])
    assert [result.status for result in results] == ["failed", "configured"]
```

- [ ] **Step 2: Run** `uv run pytest tests/cli/test_setup_wizard.py -v`; confirm both cases fail before wizard code exists.
- [ ] **Step 3: Implement** the callback, scan, menu, and Add flow. Import `dataclass`, `Path`, and the Task 1 safety interfaces in the wizard module. Show each detected target's location and configuration status, with one combined Codex/ChatGPT target; skip Alef. Use questionary checkbox choices with an explicit Select all action. Treat both `KeyboardInterrupt` and a questionary `None` response as cancellation; stop remaining actions, summarize completed work, and exit 130. Show any Codex repair reason and ask before passing `repair=True`. Let the optional skill step choose user/project once, default user, then preselect eligible MCP selections and offer all detected skill-capable tools. Deduplicate by resolved install path. Reuse `_setup_json` for the JSON branch. Clipboard commands are `pbcopy` on macOS, `clip` on Windows, and `wl-copy`/`xclip -selection clipboard` on Linux when available; do not claim copying on failure.

```python
@dataclass(frozen=True)
class SetupTarget:
    id: str
    label: str
    installed: bool
    configured: bool
    destination: Path | None
    skill_id: str | None
    repair_reason: str | None = None

@dataclass(frozen=True)
class SetupResult:
    id: str
    status: str
    destination: Path | None
    backup_paths: tuple[Path, ...]
    message: str

def run_add(selected: list[str]) -> list[SetupResult]:
    results: list[SetupResult] = []
    targets = {target.id: target for target in scan_mcp_targets()}
    for client in selected:
        destination = targets[client].destination
        if targets[client].configured and targets[client].repair_reason is None:
            results.append(SetupResult(client, "already", destination, (), "Already configured"))
            continue
        configured = False
        with capture_backups() as recorded:
            try:
                configured = add_one_mcp(client, repair=targets[client].repair_reason is not None)
                status = "configured" if configured else "failed"
                message = "Configured" if configured else "Setup failed"
            except (OSError, ConfigParseError, ValueError) as exc:
                status, message = "failed", str(exc)
        if not configured and client == "codex" and not targets[client].configured and _is_already_configured("codex"):
            status, message = "partial", "Codex entry exists, but timeout setup failed; inspect the backup"
        results.append(SetupResult(client, status, destination, tuple(recorded), message))
    return results

@app.callback(invoke_without_command=True)
def setup_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    from notebooklm_tools.cli.commands.setup_wizard import run_setup_wizard
    raise typer.Exit(run_setup_wizard())
```

- [ ] **Step 4: Run** `uv run pytest tests/cli/test_setup_wizard.py tests/cli/test_setup_codex_desktop.py tests/cli/test_setup_github_copilot.py -v`; confirm Add, JSON, and direct setup commands pass.
- [ ] **Step 5: Commit** wizard Add/JSON, dependencies, docs, and tests: `git commit -m "feat(setup): launch guided add wizard"`.

### Task 6: Remove wizard flow and final verification

**Files:**
- Modify: `src/notebooklm_tools/cli/commands/setup_wizard.py`
- Modify: `src/notebooklm_tools/cli/commands/setup.py` (safe removal result reporting)
- Modify: `docs/CLI_GUIDE.md` and `src/notebooklm_tools/cli/ai_docs.py` (removal and recovery instructions)
- Test: `tests/cli/test_setup_wizard.py`
- Test: `tests/cli/test_setup_safety.py`

**Interfaces:**
- Adds `scan_removable() -> list[SetupTarget]`, `remove_mcp_targets(targets: list[SetupTarget]) -> list[SetupResult]`, `remove_skill_targets(targets: list[SetupTarget]) -> list[SetupResult]`, `skipped(targets: list[SetupTarget]) -> list[SetupResult]`, and `run_remove(selected: list[str]) -> list[SetupResult]` to Task 5's wizard API.
- Remove scans recognized NLM MCP entries in known user/app config locations and NLM skills in both user and current-project locations. It does not walk arbitrary project directories. It prints exact paths, requests an explicit default-No confirmation for MCP removal, and a separate default-No warning for skill deletion. Shared Codex/ChatGPT and shared `agents` skill destinations appear once.

- [ ] **Step 1: Write failing tests** for separate MCP/skill selection, Select all found, default-No cancellation, each Claude Desktop profile appearing as its own removable row, desktop-only Codex removal, user/global Copilot removal, JSONC manual-removal message, a shared `agents` skill row warning that removal affects Codex/ChatGPT/Gemini, skill directory backup before removal, backup failure skip, unrelated MCP preservation, and Ctrl+C after one completed target with exit 130 and no leftover temp files.

```python
def test_remove_backup_failure_keeps_skill(monkeypatch, tmp_path):
    skill_dir = tmp_path / "nlm-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: nlm-skill\n---\n")
    monkeypatch.setitem(skill.TOOL_CONFIGS, "agents", {"user": skill_dir, "format": "skill.md"})
    monkeypatch.setattr(skill, "backup_existing", lambda *a, **kw: (_ for _ in ()).throw(PermissionError("backup denied")))
    result = skill.skill_action("agents", "user", "remove", confirm_replace=lambda _: True)
    assert result.status == "failed"
    assert (skill_dir / "SKILL.md").exists()
```

- [ ] **Step 2: Run** `uv run pytest tests/cli/test_setup_wizard.py -v`; confirm new removal tests fail.
- [ ] **Step 3: Implement** Remove selection and confirmations. Route each MCP target to its adapter's safe removal and each skill target to Task 4's internal operation. List Claude Desktop regular and Relay AI/3P profiles separately and pass the selected `profile` to `_remove_single` so removal never asks an unplanned nested profile question. Collect backup paths and per-target errors without aborting later selections. Catch `KeyboardInterrupt`, finish the summary, and exit 130. Show manual instructions when JSONC cannot be safely edited. Never recursively delete a shared parent directory.

```python
results = []
if mcp_targets:
    allowed = questionary.confirm("Remove the selected MCP entries?", default=False).ask()
    results.extend(remove_mcp_targets(mcp_targets) if allowed else skipped(mcp_targets))
if skill_targets:
    allowed = questionary.confirm("Delete the listed skill folders? Personal edits in the active folders will be removed.", default=False).ask()
    results.extend(remove_skill_targets(skill_targets) if allowed else skipped(skill_targets))
return results

def remove_mcp_targets(targets: list[SetupTarget]) -> list[SetupResult]:
    results = []
    for target in targets:
        client, _, profile = target.id.partition(":")
        with capture_backups() as recorded:
            try:
                removed = _remove_single(
                    client,
                    profile=profile or None,
                    scope="user" if client == "github-copilot" else "project",
                )
                status, message = ("removed", "Removed") if removed else ("failed", "Removal failed")
            except (OSError, ConfigParseError, ValueError) as exc:
                status, message = "failed", str(exc)
        results.append(SetupResult(target.id, status, target.destination, tuple(recorded), message))
    return results

def remove_skill_targets(targets: list[SetupTarget]) -> list[SetupResult]:
    results = []
    for target in targets:
        _, tool, level = target.id.split(":", 2)
        outcome = skill_action(tool, level, "remove", confirm_replace=lambda _: True)
        backups = (outcome.backup_path,) if outcome.backup_path else ()
        results.append(SetupResult(target.id, outcome.status, target.destination, backups, outcome.message))
    return results

def skipped(targets: list[SetupTarget]) -> list[SetupResult]:
    return [SetupResult(t.id, "skipped", t.destination, (), "Cancelled") for t in targets]
```

- [ ] **Step 4: Run** `uv run pytest tests/cli/test_setup_wizard.py tests/cli/test_setup_safety.py tests/cli/test_setup_codex_desktop.py tests/cli/test_setup_github_copilot.py tests/cli/test_skill_install.py -v`, then `uv run pytest`. Confirm all pass. Do a terminal smoke check with `uv run nlm setup --help` and a mocked/home-isolated wizard run; do not change the real user's MCP configs or skills.
- [ ] **Step 5: Commit** removal, docs, and tests: `git commit -m "feat(setup): add safe guided removal"`.

## Completion check

Before handing the branch back, run `git diff --check`, `git status --short`, `uv run pytest`, and the CLI help smoke check. Report the commit list, exact test results, any manual limitations (especially custom VS Code profiles and JSONC removal), and the backup/restore location. Do not merge or reinstall into the user's active tool environment while the unpublished main-checkout fixes are still being tested.
