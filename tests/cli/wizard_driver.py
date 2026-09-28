"""Drive the real `nlm setup` wizard in a pseudo-terminal against a sandboxed home.

Used by test_setup_wizard_e2e.py. The wizard runs as a real subprocess with a
real TTY, so prompt_toolkit key handling (Esc, arrows, Space) is exercised for
real. Everything it touches lives under a throwaway directory:

- HOME points at <root>/home, so every config file and skill lands there.
- PATH starts with <root>/bin, which holds fake `claude`, `codex`, `ps` and
  `pbcopy` programs. The fakes record their calls, `claude mcp add/remove/list`
  edits the sandboxed ~/.claude.json like the real CLI, `ps` reports no running
  Claude Desktop (unless told otherwise), and `pbcopy` writes to a file instead
  of the real clipboard.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import pexpect
import pyte

from notebooklm_tools import __version__

VENV_BIN = Path(sys.executable).parent
NLM = VENV_BIN / "nlm"
SERVER_BIN = str(VENV_BIN / "notebooklm-mcp")

UP, DOWN, ENTER, SPACE, ESC = "\x1b[A", "\x1b[B", "\r", " ", "\x1b"

_ANSI = re.compile(r"\x1b(\[[0-?]*[ -/]*[@-~]|\][^\x07]*\x07|[()][0-9A-Za-z]|[=>78DEHM])")

_CLAUDE_SHIM = """
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ["WIZ_SHIM_LOG"], "a") as log:
    log.write("claude " + " ".join(args) + "\\n")
if os.environ.get("WIZ_CLAUDE_FAIL"):
    sys.stderr.write("simulated failure\\n")
    sys.exit(1)
cfg = pathlib.Path(os.environ["HOME"]) / ".claude.json"
data = json.loads(cfg.read_text()) if cfg.exists() else {}
servers = data.setdefault("mcpServers", {})
positional = [a for a in args[2:] if not a.startswith("-") and a not in ("user", "local", "project")]
if args[:2] == ["mcp", "add"]:
    sep = args.index("--")
    servers[args[sep - 1]] = {"command": args[sep + 1]}
    cfg.write_text(json.dumps(data))
elif args[:2] == ["mcp", "add-json"]:
    name, payload = positional[0], positional[1]
    if name in servers:
        sys.stderr.write(f"MCP server {name} already exists\\n")
        sys.exit(1)
    servers[name] = json.loads(payload)
    cfg.write_text(json.dumps(data))
elif args[:2] == ["mcp", "remove"]:
    for n in positional:
        servers.pop(n, None)
    cfg.write_text(json.dumps(data))
elif args[:2] == ["mcp", "list"]:
    for n, e in servers.items():
        print(f"{n}: {e.get('command', '')}")
"""

_LOG_SHIM = """
import os, sys
with open(os.environ["WIZ_SHIM_LOG"], "a") as log:
    log.write("{name} " + " ".join(sys.argv[1:]) + "\\n")
"""

_PS_SHIM = """
import os
if os.environ.get("WIZ_CLAUDE_DESKTOP_RUNNING"):
    print("  999     1 /Applications/Claude.app/Contents/MacOS/Claude")
"""

_PBCOPY_SHIM = """
import os, sys
with open(os.environ["WIZ_CLIPBOARD"], "w") as f:
    f.write(sys.stdin.read())
"""


class Sandbox:
    """A throwaway home + fake tool binaries for one wizard run."""

    def __init__(self, root: Path):
        self.root = root
        self.home = root / "home"
        self.bin = root / "bin"
        self.project = root / "project"
        self.shim_log = root / "shim.log"
        self.clipboard = root / "clipboard.txt"
        for d in (self.home, self.bin, self.project):
            d.mkdir(parents=True, exist_ok=True)
        self.shim_log.touch()
        self._write_shim("codex", _LOG_SHIM.replace("{name}", "codex"))
        self._write_shim("ps", _PS_SHIM)
        self._write_shim("pbcopy", _PBCOPY_SHIM)
        self._write_shim("open", _LOG_SHIM.replace("{name}", "open"))  # no real Finder
        # Pre-seed the version-check cache so the wizard never hits the network.
        cache = self.home / ".notebooklm-mcp-cli" / "cache" / "update_check.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"latest_version": __version__, "checked_at": time.time()}))
        self.extra_env: dict[str, str] = {}

    def _write_shim(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text(f"#!{sys.executable}\n{body}")
        path.chmod(0o755)

    # --- tools "installed" in the sandbox ---------------------------------

    def install_claude_code(self) -> None:
        self._write_shim("claude", _CLAUDE_SHIM)

    def install_codex(self) -> None:
        (self.home / ".codex").mkdir(exist_ok=True)

    def install_claude_desktop(self, profiles: tuple[str, ...] = ("Claude",)) -> None:
        for name in profiles:
            (self.home / "Library" / "Application Support" / name).mkdir(
                parents=True, exist_ok=True
            )

    def install_cursor(self) -> None:
        (self.home / ".cursor").mkdir(exist_ok=True)

    # --- files the wizard writes -------------------------------------------

    @property
    def claude_json(self) -> dict:
        path = self.home / ".claude.json"
        return json.loads(path.read_text()) if path.exists() else {}

    @property
    def codex_toml(self) -> str:
        path = self.home / ".codex" / "config.toml"
        return path.read_text() if path.exists() else ""

    def claude_desktop_config(self, profile: str = "Claude") -> dict:
        path = (
            self.home / "Library" / "Application Support" / profile / "claude_desktop_config.json"
        )
        return json.loads(path.read_text()) if path.exists() else {}

    @property
    def cursor_config(self) -> dict:
        path = self.home / ".cursor" / "mcp.json"
        return json.loads(path.read_text()) if path.exists() else {}

    @property
    def shim_calls(self) -> list[str]:
        return [line for line in self.shim_log.read_text().splitlines() if line]

    def env(self) -> dict[str, str]:
        env = {
            "HOME": str(self.home),
            "PATH": f"{self.bin}:{VENV_BIN}:/usr/bin:/bin",
            "TERM": "xterm-256color",
            "LANG": "en_US.UTF-8",
            "WIZ_SHIM_LOG": str(self.shim_log),
            "WIZ_CLIPBOARD": str(self.clipboard),
        }
        env.update(self.extra_env)
        return env


class Wizard:
    """A running `nlm setup` session with a rendered virtual screen."""

    ROWS, COLS = 60, 160

    def __init__(self, sandbox: Sandbox, timeout: float = 20):
        self.sandbox = sandbox
        self.screen = pyte.Screen(self.COLS, self.ROWS)
        self._stream = pyte.Stream(self.screen)
        self.transcript: list[str] = []
        self._cursor = 0  # position in plain_output() already matched by expect()
        self.child = pexpect.spawn(
            str(NLM),
            ["setup"],
            cwd=str(sandbox.project),
            env=sandbox.env(),
            dimensions=(self.ROWS, self.COLS),
            encoding="utf-8",
            codec_errors="replace",
            timeout=timeout,
        )
        self.timeout = timeout
        self.child.logfile_read = self

    # pexpect logfile protocol: every byte the wizard prints is rendered too.
    def write(self, data: str) -> None:
        self.transcript.append(data)
        self._stream.feed(data)

    def flush(self) -> None:
        pass

    # --- syncing --------------------------------------------------------------

    def plain_output(self) -> str:
        """Everything printed so far, with terminal control codes stripped."""
        return _ANSI.sub("", "".join(self.transcript))

    def _pump(self, timeout: float) -> bool:
        """Read whatever is available; False once the wizard has exited."""
        try:
            self.child.read_nonblocking(65536, timeout=timeout)
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF:
            return False
        return True

    def expect(self, pattern: str, timeout: float | None = None) -> re.Match:
        """Wait for output (after the last match) matching regex `pattern`."""
        deadline = time.time() + (timeout or self.timeout)
        regex = re.compile(pattern)
        while True:
            match = regex.search(self.plain_output(), self._cursor)
            if match:
                self._cursor = match.end()
                return match
            alive = self._pump(0.1)
            if not alive or time.time() > deadline:
                match = regex.search(self.plain_output(), self._cursor)
                if match:
                    self._cursor = match.end()
                    return match
                reason = "wizard exited" if not alive else "timed out"
                raise AssertionError(
                    f"{reason} waiting for {pattern!r}.\n--- screen ---\n{self.text()}"
                )

    def settle(self, quiet: float = 0.15, limit: float = 5) -> None:
        """Read until the wizard stops printing for `quiet` seconds."""
        deadline = time.time() + limit
        while time.time() < deadline:
            before = len(self.transcript)
            if not self._pump(quiet) or len(self.transcript) == before:
                return

    def send(self, *keys: str, gap: float = 0.05) -> None:
        for key in keys:
            self.child.send(key)
            time.sleep(gap)

    def esc(self) -> None:
        # A lone Esc needs a beat so it isn't glued to the next key as an escape sequence.
        self.child.send(ESC)
        time.sleep(0.3)

    # --- screen reading -------------------------------------------------------

    def lines(self) -> list[str]:
        return [line.rstrip() for line in self.screen.display]

    def text(self) -> str:
        return "\n".join(self.lines())

    def choice_lines(self, last_question: str) -> list[str]:
        """Screen lines of the list under the most recent `last_question`."""
        lines = self.lines()
        start = max(i for i, line in enumerate(lines) if last_question in line)
        out = []
        for line in lines[start + 1 :]:
            if not line.strip():
                break
            out.append(line)
        return out

    def pointed(self, question: str) -> str:
        """The list line the pointer (») is on."""
        for line in self.choice_lines(question):
            if line.lstrip().startswith("»"):
                return line
        raise AssertionError(f"No pointer under {question!r}:\n{self.text()}")

    def move_to(self, question: str, label: str, max_steps: int = 20) -> None:
        """Press Down until the pointer sits on the line containing `label`."""
        self.settle()
        for _ in range(max_steps):
            if label in self.pointed(question):
                return
            self.send(DOWN)
            self.settle(quiet=0.08)
        raise AssertionError(f"Could not reach {label!r} under {question!r}:\n{self.text()}")

    def ticked(self, question: str) -> list[str]:
        """Labels whose checkbox shows ● under `question`."""
        return [line for line in self.choice_lines(question) if "●" in line]

    def pick(self, question: str, *labels: str) -> None:
        """Checkbox: tick each label (Space), then confirm (Enter)."""
        for label in labels:
            self.move_to(question, label)
            self.send(SPACE)
        self.send(ENTER)

    def choose(self, question: str, label: str) -> None:
        """Select list: move to `label` and press Enter."""
        self.move_to(question, label)
        self.send(ENTER)

    # --- ending ---------------------------------------------------------------

    def finish(self) -> int:
        deadline = time.time() + self.timeout
        while self._pump(0.1):
            if time.time() > deadline:
                raise AssertionError(f"wizard did not exit.\n--- screen ---\n{self.text()}")
        self.child.close()
        return self.child.exitstatus

    def quit(self) -> int:
        """From the main menu (already on screen): pick Exit."""
        self.choose("What would you like to do", "Exit")
        return self.finish()

    def close(self) -> None:
        if self.child.isalive():
            self.child.terminate(force=True)


def env_without_real_tools() -> None:
    """Assert the sandbox PATH can't reach real claude/codex installs."""
    for d in ("/usr/bin", "/bin"):
        for tool in ("claude", "codex", "cursor", "code", "gemini", "opencode"):
            assert not os.path.exists(os.path.join(d, tool)), f"real {tool} found in {d}"
