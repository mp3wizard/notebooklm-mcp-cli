# NotebookLM CLI & MCP Server

![NotebookLM MCP Header](docs/media/header.jpg)

[![PyPI version](https://img.shields.io/pypi/v/notebooklm-mcp-cli)](https://pypi.org/project/notebooklm-mcp-cli/)
[![PyPI downloads](https://img.shields.io/pypi/dm/notebooklm-mcp-cli)](https://pypistats.org/packages/notebooklm-mcp-cli)
[![Total downloads](https://static.pepy.tech/badge/notebooklm-mcp-cli)](https://pepy.tech/projects/notebooklm-mcp-cli)
[![Python](https://img.shields.io/pypi/pyversions/notebooklm-mcp-cli)](https://pypi.org/project/notebooklm-mcp-cli/)
[![License](https://img.shields.io/pypi/l/notebooklm-mcp-cli)](https://github.com/jacob-bd/notebooklm-mcp-cli/blob/main/LICENSE)

> 🎉 **January 2026 — Major Update!** This project has been completely refactored to unify **NotebookLM-MCP** and **NotebookLM-CLI** into a single, powerful package. One install gives you both the CLI (`nlm`) and MCP server (`notebooklm-mcp`). See the [CLI Guide](docs/CLI_GUIDE.md) and [MCP Guide](docs/MCP_GUIDE.md) for full documentation.

## What's New (mp3wizard fork)

### Upstream sync (v0.6.10 — May 2026)
- **Windows CDP authentication reliability (PR #192, @jonathanzhan1975)** — unifies browser detection in `doctor.py` to match `cdp.py` (Edge supported), reduces CDP port scan timeout 2s → 1s to prevent Windows blocking, adds `CREATE_NEW_PROCESS_GROUP` flag for Windows process isolation, disables Edge Startup Boost via `--disable-features=msEdgeStartupBoost`, introduces `_kill_stale_nlm_browsers` to clean zombie CDP processes, and improves `_summarize_browser_startup_failure` to log exit codes
- **Merge note** — kept local's `# nosec B603` justification on the `subprocess.Popen(args, **kwargs)` call in `cdp.py` while adopting upstream's new `kwargs` (Windows `creationflags`) form
- **AGENTS.md** — new upstream contributor guide (260 lines) added at repo root

### Security scan (May 2026 — v0.6.10)
- Full automated scan post-merge: Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog, OSV-Scanner
- **0 HIGH / 0 MEDIUM** — clean
- **3 Low (accepted, not fixed)** — all in newly merged `_kill_process()` (`utils/cdp.py:940-951`): B607 partial path `taskkill` (Windows System32 built-in, not user-controlled), B603 subprocess call (hardcoded args + integer PID), B110 `try/except/pass` (intentional "best effort" semantics, documented in docstring)
- **0 secrets** in git history (534 commits, 9.31 MB; Gitleaks + TruffleHog verified)
- **0 SAST findings** (Semgrep OWASP+Python+Secrets / 101 files)
- **0 dependency vulnerabilities** (Trivy + OSV-Scanner over 89 packages in `uv.lock`)
- **Overall risk posture: Clean** (full report: `docs/security-scan-report-2026-05-18.md`)

### Upstream sync (v0.6.9 — May 2026)
- **EPUB file upload support (PR #191, @mateogon)** — `.epub` files can now be uploaded as notebook sources
- **Hermes Agent support** — `nlm skill install hermes` installs the NotebookLM skill for NousResearch's Hermes Agent; respects `$HERMES_HOME`
- **Windows hardening** — fixed false "tool not installed" warnings, `PermissionError` now yields an actionable `icacls` hint instead of a traceback, and all file I/O specifies `encoding="utf-8"` to prevent `UnicodeDecodeError` on cp1252 systems
- **CLI studio status mind maps (fix)** — `nlm studio status` routes through the service layer so mind maps appear in the output
- **Refactor** — shared `is_tool_on_system()` helper in `cli/utils.py`; `TOOL_CONFIGS` now uses a typed `ToolConfig` `TypedDict`

### Security scan (May 2026 — v0.6.9)
- Full automated scan post-merge: Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog, OSV-Scanner
- **2 HIGH + 1 MEDIUM fixed** — `urllib3` 2.6.3 → **2.7.0** (CVE-2026-44431 CVSS 8.9 cross-origin header leak; CVE-2026-44432 CVSS 8.2 decompression-bomb bypass); `authlib` 1.6.11 → **1.7.2** (CVE-2026-44681 CVSS 6.1 OIDC open redirect). Re-scan: clean
- **3 Low fixed** — Bandit B110 `try/except/pass` retry loops in `cli/main.py` + `utils/cdp.py` annotated with `# nosec B110` + justification
- **0 secrets** in git history (530 commits, 9.29 MB; Gitleaks + TruffleHog)
- **0 SAST findings** (Semgrep OWASP+Python+Secrets / 101 files; Bandit 22,782 LOC — 0 issues after annotation)
- **Overall risk posture: Clean** after fixes (full report: `docs/security-scan-report-2026-05-14.md`)

### Upstream sync (v0.6.6 + cited research import — May 2026)
- **Cited research source import (PR #188, @zxyasfas)** — new feature to import cited sources from a research run directly back into the notebook (services/research.py + CLI/MCP wrappers + docs)
- **Opaque throttle errors fixed (Issue #182)** — `RPCError code=8` (RESOURCE_EXHAUSTED) with a `UserDisplayableError` payload now surfaces the human-readable message instead of the raw protobuf type URL; new `ResourceExhaustedError(RPCError)` subclass; studio creation provides retry-specific hints
- **Cinematic `--style-prompt` honored (Issue #183, @guia-matthieu)** — `--style-prompt` with cinematic format now maps to `custom_instructions` (web UI's "Customize Video Overview" field). Validation runs before source resolution; clearer error pointing to `--focus` when `--style`/`--style-prompt` rejected
- **Login race-condition fix (Issue #181, v0.6.5)** — `nlm login` and headless flows now use deterministic DOM polling for `FdrFJe` / build label before extracting cookies, eliminating premature exit and "Authentication expired"
- **Docs** — Google AI Ultra ($249/mo) added to tested tiers (PR #184)

### Security scan (May 2026 — v0.6.6)
- Full automated scan post-merge: Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog, OSV-Scanner, config-audit, skill-audit, mcp-exfil-scan
- **1 HIGH fixed** — `python-multipart` 0.0.26 → **0.0.28** (CVE-2026-42561, GHSA-pp6c-gr5w-3c5g, CVSS 7.5: DoS via unbounded multipart part headers). Re-scan: clean
- **0 secrets** in git history (521 commits, 9.19 MB; Gitleaks + TruffleHog)
- **0 SAST findings** (Semgrep OWASP+Python+Secrets / 101 files; Bandit 22,679 LOC — 2 Low retry-loop `try/except/pass` left as-is)
- **Overall risk posture: Clean** after fix (full report: `docs/security-scan-report-2026-05-10.md`)

### Upstream sync (v0.6.4 — May 2026)
- **Cross-domain artifact downloads (PR #180, @laofun)** — Fixed an authentication bug where `OSID` / `__Secure-OSID` cookies leaked during cross-domain artifact downloads (e.g. redirects from `notebooklm.google.com` to `lh3.googleusercontent.com`), causing `ServiceLogin` redirects and HTML login pages instead of the actual file. `_download_url` now strips service-scoped cookies for external Google hosts while preserving other auth cookies
- **CI hygiene** — manifest version aligned across `desktop-extension/manifest.json`; `cdp.py` reformatted to satisfy ruff format CI gate

### Security scan (May 2026 — v0.6.4)
- Full automated scan post-merge: Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog, OSV-Scanner
- **0 vulnerabilities** in uv.lock (88 packages, Trivy + OSV-Scanner)
- **0 secrets** in git history (512 commits, 9.16 MB; Gitleaks + TruffleHog)
- **0 SAST findings** (Semgrep 542 rules / 101 files; Bandit 22,414 LOC)
- **Overall risk posture: Clean** — no fixes required (full report: `docs/security-scan-report-2026-05-05.md`)

### Upstream sync (v0.6.3 — May 2026)
- **CDP tab creation fallback (#175)** — `nlm login` now reuses an existing tab if CDP `Target.createTarget` fails (e.g. in locked-down environments where new-tab creation is blocked by enterprise policy). The reuse path is consolidated into a single pass that picks the freshest existing page
- **GitHub Copilot setup target (#178, @whatnick)** — `nlm setup` now supports `--client github-copilot`, installing the skill files into the GitHub Copilot config path

### Security scan (May 2026 — v0.6.3)
- Full automated scan post-merge: Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog
- **0 vulnerabilities** in uv.lock (Trivy fs)
- **0 secrets** in git history (507 commits, 9.15 MB; Gitleaks + TruffleHog)
- **0 SAST findings** (Semgrep 542 rules / 101 files; Bandit 22,409 LOC)
- **Overall risk posture: Clean** — no fixes required (full report: `docs/security-scan-report-2026-05-04.md`)

### Upstream sync (v0.6.2 — April 2026)
- **Login timeout fix (#174, @SKMKZP)** — `is_logged_in()` now parses URL hostname via `urlparse()` instead of substring-matching the full URL, fixing post-sign-in false-negative when the redirect URL contains `original_referer=...accounts.google.com...` in the query string
- **Headless browser hijacking fix** — `find_any_existing_cdp_browser()` now skips browsers whose User-Agent contains `HeadlessChrome` (e.g. Perplexity MCP), preventing `nlm login` from silently hanging 5 minutes on an invisible browser
- **Silent login wait loop** — CLI now emits "Still waiting for sign-in... (Ns elapsed)" every 30s during the login wait (combined with local SEC-007 transient-error logging in the merge resolution)
- **Refactor** — extracted `_fetch_cdp_version()` helper to share `/json/version` logic between `get_debugger_url()` and `find_any_existing_cdp_browser()`

### Upstream sync (v0.6.1 — April 2026)
- **Label reorganize support** — new `reorganize_labels` action (core/service/MCP/CLI). Mode `[1]` reorganizes all sources (replaces all labels, requires confirm); mode `[0]` only labels sources not yet categorized. `_require_notebook_id()` helper extracted to deduplicate validation. `docs/API_REFERENCE.md` updated with both modes

### Security scan (May 2026 — v0.6.2)
- Full automated scan post-merge: Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog, OSV-Scanner
- **0 vulnerabilities** in uv.lock (88 packages, Trivy + OSV-Scanner)
- **0 secrets** in git history (501 commits, 9.13 MB; Gitleaks + TruffleHog)
- **0 SAST findings** (Semgrep 542 rules / 101 files; Bandit 22,312 LOC)
- **Overall risk posture: Clean** — no fixes required

### Upstream sync (v0.6.0 — April 2026)
- **Source Label Management** — organize notebook sources into thematic categories with the new `label` MCP tool and `nlm label` CLI commands. Actions: `auto` (AI-generated labels), `list`, `create`, `rename`, `set_emoji`, `move_source`, `delete`. Multi-label assignment supported (≥5 sources required for auto-labeling)
- **EOF on initialization fix** (v0.5.31, Issue #171) — `_StdoutToStderrWrapper` in `server.py` redirects stray text output to stderr so the stdio JSON-RPC channel stays clean (fixes EOF crashes on Windows/macOS)
- **WSL firewall encoding fix** (PR #172, @andrepreira) — `check_firewall_rule()` now handles UTF-16-LE PowerShell output, eliminating the false firewall warning during `nlm login --wsl`

### Security scan (April 2026 — v0.6.0)
- Full automated scan post-merge: Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog, OSV-Scanner
- **0 vulnerabilities** in uv.lock (88 packages scanned by Trivy + OSV-Scanner)
- **0 secrets** in git history (495 commits, Gitleaks + TruffleHog)
- **0 SAST findings** (Semgrep on 101 Python files, 191 rules; Bandit on `src/` + `scripts/`)
- **Overall risk posture: Clean** — no fixes required

### Upstream sync (v0.5.30 — April 2026)
- **Stale `NOTEBOOKLM_COOKIES` auth loop fix** (Issue #170) — `refresh_auth` now returns an actionable error when `NOTEBOOKLM_COOKIES` env var is set, instead of silently returning false success; auth failure messages now mention the env var as the likely cause
- **Deprecated env vars removed** — `NOTEBOOKLM_CSRF_TOKEN` and `NOTEBOOKLM_SESSION_ID` are no longer read; both values are auto-extracted and stale env vars would bypass auto-refresh
- **Auth troubleshooting docs** — new section in `docs/AUTHENTICATION.md` covering the env var auth trap

### Security scan (April 2026 — v0.5.30)
- Full automated scan post-merge: Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog, OSV-Scanner, config-audit, skill-audit, mcp-exfil-scan
- **0 vulnerabilities** in uv.lock (88 packages scanned by Trivy + OSV-Scanner)
- **0 secrets** in git history (489 commits, Gitleaks + TruffleHog)
- **0 SAST findings** (Semgrep OWASP/Python/Secrets, Bandit src/)
- Suppressed 2 confirmed Bandit false positives with `# nosec` annotations (`B105` in `_utils.py`, `B110` in `sources.py`)
- **Overall risk posture: Clean**

### Upstream sync (v0.5.27 — April 2026)
- **Source `--title` fix** (PR #162, @CryptoWombat) — adding a file source via `nlm add file --title` now honours the custom title; race condition on `wait=True` also fixed
- **Restore skill targets** (Issue #163) — `codex` and `gemini-cli` skill targets restored; Alef Agent-specific frontmatter added

### Security scan (April 2026 — v0.5.27)
- Full automated scan post-merge: Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog, OSV-Scanner, config-audit, mcp-exfil-scan
- **python-dotenv upgraded 1.2.1 → 1.2.2** — fixes CVE-2026-28684 / GHSA-mf9w-mj56-hr94 (Medium, CVSS 6.6)
- **Overall risk posture: Clean** — 0 vulnerabilities after fix, 0 secrets in git history, 0 SAST findings
- See [docs/security-scan-report-2026-04-22.md](docs/security-scan-report-2026-04-22.md) for full report

### Upstream sync (v0.5.26 — April 2026)
- **MCP auth auto-reload** (Issue #161) — MCP client now reloads automatically when cached tokens on disk are newer than the in-memory client; no more manual server restarts after `nlm login`
- **`server_info` auth status** (Issue #160) — `server_info` tool now returns `auth_status` with local token presence and age
- **CLI Rich Windows fix** (Issue #156 follow-up, @argonaut-cm) — all CLI Rich output now routes through `make_console()`; `Formatter` default uses correct console instance on Windows

### Security scan (April 2026 — v0.5.26)
- Full automated scan post-merge: Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog, OSV-Scanner, config-audit, skill-audit, mcp-exfil-scan
- **authlib upgraded 1.6.9 → 1.6.11** — fixes GHSA-jj8c-mmj3-mmgv (Medium, CVSS 5.4)
- **Bandit suppression** — added `# nosec` annotations for type-narrowing asserts, optional mind-map exception, and WSL fixed-path subprocess calls; src/ now 0 issues at all severity levels
- See [docs/security-scan-report-2026-04-18.md](docs/security-scan-report-2026-04-18.md) for full report

### Upstream sync (v0.5.25 — April 2026)
- **Audio download CDN fix** (Issue #158) — prefers `-dv` download variant URL (~3 MB/s CDN) over streaming transcode URL (~30 KB/s); 47 MB file downloads in ~15s
- **CDP WebSocket proxy bypass** (Issue #119, PR #157) — `nlm login` no longer breaks when `HTTP_PROXY`/`HTTPS_PROXY` are set (Clash, Surge, etc.); proxy env vars are cleared around localhost CDP connections
- **Windows UTF-8 fix** (Issue #156) — MCP server no longer crashes with `UnicodeEncodeError` on Windows cp1252 consoles when NotebookLM returns Unicode characters like `→`; stdout/stderr reconfigured to UTF-8 at startup
- **Lazy-load `NotebookLMClient`** — deferred import keeps stdio encoding bootstrap lightweight
- **CI release gate** — new workflow validates all version strings are aligned before release

### Security scan (April 2026 — v0.5.25)
- Full automated scan post-merge: Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog, OSV-Scanner, config-audit, skill-audit, mcp-exfil-scan
- **Overall risk posture: Clean** — 0 vulnerabilities in 88 packages (Trivy + OSV-Scanner), 0 secrets in git history (Gitleaks + TruffleHog), 0 SAST findings (Semgrep + Bandit)
- See [docs/security-scan-report-2026-04-16.md](docs/security-scan-report-2026-04-16.md) for full report

### Upstream sync (v0.5.21–v0.5.22 — April 2026)
- **HTTP 400 as auth failure** (Issue #147) — Google returns 400 when CSRF token expires instead of 401/403; now triggers Layer-1 auth recovery instead of raw traceback
- **Chromium auth resilience** (PR #144) — improved stability; removed Firefox login support
- **Source alias autodetect fix** (Issue #145) — fixed alias detection using legacy client method that no longer exists
- **REPL source counts fix** — startup banner now shows correct source count
- **Audio status=2 readiness** — audio with status=2 + media URLs correctly reported as "ready"
- **Studio audio URL extraction** — uses media list for audio artifacts; falls back to legacy direct slot

### Security scan (April 2026 — v0.5.22)
- Full automated scan post-merge: Gitleaks, Bandit, Semgrep (OWASP/Python/Secrets), Trivy, TruffleHog, OSV-Scanner, config-audit, skill-audit, mcp-exfil-scan
- **Overall risk posture: Clean** — 0 vulnerabilities in Trivy after upgrade, 0 secrets in git history
- 12 CVEs resolved across 6 packages (2 Critical, 7 High, 3 Medium/Low)
- `diskcache` and `lupa` (unfixable CVEs) removed as transitive deps via fastmcp 3.x upgrade

### Security fixes (April 2026 — v0.5.22)
- **authlib upgraded 1.6.6 → 1.6.9** — fixes CVE-2026-27962 (CRITICAL: JWK Header Injection auth bypass), CVE-2026-28490 (HIGH: JWE padding oracle), CVE-2026-28498 (HIGH: forged OpenID Connect tokens), CVE-2026-28802 (HIGH: JWT signature verification bypass)
- **fastmcp upgraded 2.14.2 → 3.2.3** — fixes CVE-2026-32871 (CRITICAL: SSRF/Path Traversal), CVE-2026-27124 (HIGH: OAuth confused deputy), CVE-2025-64340 (MEDIUM: Gemini CLI command injection); also removes `diskcache` (CVE-2025-69872) and `lupa` (CVE-2026-34444) transitive deps
- **cryptography upgraded 46.0.3 → 46.0.7** — fixes CVE-2026-26007 (HIGH: SECT curve subgroup attack), CVE-2026-39892 (MEDIUM), CVE-2026-34073 (LOW: DNS constraint bypass)
- **pyjwt upgraded 2.10.1 → 2.12.1** — fixes CVE-2026-32597 (HIGH: accepts unknown `crit` header extensions)
- **python-multipart upgraded 0.0.21 → 0.0.26** — fixes CVE-2026-24486 (HIGH: arbitrary file write via path traversal)
- **requests upgraded 2.32.5 → 2.33.1** — fixes CVE-2026-25645 (MEDIUM: predictable temp file)
- **jaraco-context upgraded 6.0.2 → 6.1.2** — fixes GHSA-58pv-8j8x-9vj2 (HIGH, CVSS 8.6)
- **pygments upgraded 2.19.2 → 2.20.0** — fixes CVE-2026-4539 (LOW: regex DoS in AdlLexer)

### Upstream sync (v0.5.17–v0.5.20 — April 2026)
- **WSL2 authentication support** (`nlm login --wsl`) — launches Windows Chrome from WSL2 with automatic firewall management and CDP cross-boundary communication (PR #138)
- **Thread-safety for concurrent MCP tool calls** — `threading.Lock` in `BaseClient` protects mutable state from race conditions during parallel tool invocations (PR #135)
- **Auto-import for research** — `nlm research start --auto-import` waits for research to finish and immediately imports results (v0.5.19)
- **Deep Research task ID fix** (Issue #140) — resolved task ID mutation causing import failures
- **Verb-first CLI parity** — 13 missing parameters restored across `nlm create`, `nlm add`, `nlm describe`, `nlm query`, `nlm delete` commands (Issue #141/#142)
- **fastmcp widened to `>=3.2.0,<4.0`** — resolves startup crash with `fakeredis 2.35.0` (Issue #141)
- **WSL2 doctor diagnostics** — `nlm doctor` now detects WSL2 environments and reports Chrome/firewall status
- **gRPC error code mapping** — codes 5, 7, 16 now show `NOT_FOUND`, `PERMISSION_DENIED`, etc. instead of "unknown"

### Claude Code Skill (April 2026)
- **`notebooklm-cli.skill`** added — install this skill in Claude Code for AI-assisted `nlm` CLI workflows (auth, notebooks, sources, studio generation, research, batch operations, and more)
- Skill covers all 10 artifact types with format/style options, 4 common end-to-end workflows, and error recovery guidance

### Upstream sync (v0.5.11–v0.5.16)
- Enterprise/Workspace configurable base URL support
- Auth recovery fixes + CDP proxy bypass fix
- Python 3.13 compatibility fix
- `research_status` polling loop (`poll_interval`, `max_wait`)
- Async query polling fix (Issue #125)
- URL source dual RPC fallback (Issue #121)
- PEP 735 dev dependency group migration

**Programmatic access to Google NotebookLM** — via command-line interface (CLI) or Model Context Protocol (MCP) server.

> **Note:** Tested with Pro/free and Google AI Ultra ($249/mo) tier accounts. May work with NotebookLM Enterprise accounts but has not been tested.

📺 **Watch the Demos**

### Latest

| **Codex Setup + Cinematic Video & Slides** |
|:---:|
| [![Latest](https://img.youtube.com/vi/KrgLCrvU1dw/mqdefault.jpg)](https://www.youtube.com/watch?v=KrgLCrvU1dw) |

### MCP Demos

| **General Overview** | **Claude Desktop** | **Perplexity Desktop** | **MCP Super Assistant** |
|:---:|:---:|:---:|:---:|
| [![General](https://img.youtube.com/vi/d-PZDQlO4m4/mqdefault.jpg)](https://www.youtube.com/watch?v=d-PZDQlO4m4) | [![Claude](https://img.youtube.com/vi/PU8JhgLPxes/mqdefault.jpg)](https://www.youtube.com/watch?v=PU8JhgLPxes) | [![Perplexity](https://img.youtube.com/vi/BCKlDNg-qxs/mqdefault.jpg)](https://www.youtube.com/watch?v=BCKlDNg-qxs) | [![MCP SuperAssistant](https://img.youtube.com/vi/7aHDbkr-l_E/mqdefault.jpg)](https://www.youtube.com/watch?v=7aHDbkr-l_E) |

### CLI Demos

| **CLI Overview** | **CLI, MCP & Skills** | **Setup, Doctor & mcpb** | **Infographics Support** |
|:---:|:---:|:---:|:---:|
| [![CLI Overview](https://img.youtube.com/vi/XyXVuALWZkE/mqdefault.jpg)](https://www.youtube.com/watch?v=XyXVuALWZkE) | [![CLI, MCP & Skills](https://img.youtube.com/vi/ZQBQigFK-E8/mqdefault.jpg)](https://www.youtube.com/watch?v=ZQBQigFK-E8) | [![Setup, Doctor & mcpb](https://img.youtube.com/vi/5tOUilBTJ3Q/mqdefault.jpg)](https://www.youtube.com/watch?v=5tOUilBTJ3Q) | [![Infographics](https://img.youtube.com/vi/Uc6iH5NuQ9A/mqdefault.jpg)](https://www.youtube.com/watch?v=Uc6iH5NuQ9A) |


## Two Ways to Use

### 🖥️ Command-Line Interface (CLI)

Use `nlm` directly in your terminal for scripting, automation, or interactive use:

```bash
nlm notebook list                              # List all notebooks
nlm notebook create "Research Project"         # Create a notebook
nlm source add <notebook> --url "https://..."  # Add sources
nlm audio create <notebook> --confirm          # Generate podcast
nlm download audio <notebook> <artifact-id>    # Download audio file
nlm share public <notebook>                    # Enable public link
```

Run `nlm --ai` for comprehensive AI-assistant documentation.

### 🤖 MCP Server (for AI Agents)

Connect AI assistants (Claude, Gemini, Cursor, etc.) to NotebookLM:

```bash
# Automatic setup — picks the right config for each tool
nlm setup add claude-code
nlm setup add gemini
nlm setup add github-copilot
nlm setup add cursor
nlm setup add cline
nlm setup add antigravity

# Generate JSON config for any other tool
nlm setup add json
```

Then use natural language: *"Create a notebook about quantum computing and generate a podcast"*

## Features

| Capability | CLI Command | MCP Tool |
|------------|-------------|----------|
| List notebooks | `nlm notebook list` | `notebook_list` |
| Create notebook | `nlm notebook create` | `notebook_create` |
| Add Sources (URL, Text, Drive, File) | `nlm source add` | `source_add` |
| Query notebook (persists to web UI) | `nlm notebook query` | `notebook_query` |
| Create Studio Content (Audio, Video, etc.) | `nlm studio create` | `studio_create` |
| Revise slide decks | `nlm slides revise` | `studio_revise` |
| Download artifacts | `nlm download <type>` | `download_artifact` |
| Web/Drive research | `nlm research start` | `research_start` |
| Share notebook | `nlm share public/invite` | `notebook_share_*` |
| Sync Drive sources | `nlm source sync` | `source_sync_drive` |
| Batch operations | `nlm batch query/create/delete` | `batch` |
| Cross-notebook query | `nlm cross query` | `cross_notebook_query` |
| Pipelines (multi-step workflows) | `nlm pipeline run/list` | `pipeline` |
| Tag & smart select | `nlm tag add/list/select` | `tag` |
| Configure AI tools | `nlm setup add/remove/list` | — |
| Install AI Skills | `nlm skill install/update` | — |
| Diagnose issues | `nlm doctor` | — |

📚 **More Documentation:**
- **[CLI Guide](docs/CLI_GUIDE.md)** — Complete command reference
- **[MCP Guide](docs/MCP_GUIDE.md)** — All 35 MCP tools with examples
- **[Authentication](docs/AUTHENTICATION.md)** — Setup and troubleshooting
- **[API Reference](docs/API_REFERENCE.md)** — Internal API docs for contributors

## Important Disclaimer

This MCP and CLI use **internal APIs** that:
- Are undocumented and may change without notice
- Require cookie extraction from your browser (I have a tool for that!)

Use at your own risk for personal/experimental purposes.

## Installation

> 🆕 **Claude Desktop users:** [Download the extension](https://github.com/jacob-bd/notebooklm-mcp-cli/releases/latest) (`.mcpb` file) → double-click → done! One-click install, no config needed.

Install from PyPI. This single package includes **both the CLI and MCP server**:

### Using uv (Recommended)
```bash
uv tool install notebooklm-mcp-cli
```

### Using uvx (Run Without Install)
```bash
uvx --from notebooklm-mcp-cli nlm --help
uvx --from notebooklm-mcp-cli notebooklm-mcp
```

### Using pip
```bash
pip install notebooklm-mcp-cli
```

### Using pipx
```bash
pipx install notebooklm-mcp-cli
```

**After installation, you get:**
- `nlm` — Command-line interface
- `notebooklm-mcp` — MCP server for AI assistants

<details>
<summary>Alternative: Install from Source</summary>

```bash
# Clone the repository
git clone https://github.com/jacob-bd/notebooklm-mcp-cli.git
cd notebooklm-mcp

# Install with uv
uv tool install .
```
</details>

## Upgrading

```bash
# Using uv
uv tool upgrade notebooklm-mcp-cli

# Using pip
pip install --upgrade notebooklm-mcp-cli

# Using pipx
pipx upgrade notebooklm-mcp-cli
```

After upgrading, restart your AI tool to reconnect to the updated MCP server:

- **Claude Code:** Restart the application, or use `/mcp` to reconnect
- **Cursor:** Restart the application
- **Gemini CLI:** Restart the CLI session

## Upgrading from Legacy Versions

If you previously installed the **separate** CLI and MCP packages, you need to migrate to the unified package.

### Step 1: Check What You Have Installed

```bash
uv tool list | grep notebooklm
```

**Legacy packages to remove:**
| Package | What it was |
|---------|-------------|
| `notebooklm-cli` | Old CLI-only package |
| `notebooklm-mcp-server` | Old MCP-only package |

### Step 2: Uninstall Legacy Packages

```bash
# Remove old CLI package (if installed)
uv tool uninstall notebooklm-cli

# Remove old MCP package (if installed)
uv tool uninstall notebooklm-mcp-server
```

### Step 3: Reinstall the Unified Package

After removing legacy packages, reinstall to fix symlinks:

```bash
uv tool install --force notebooklm-mcp-cli
```

> **Why `--force`?** When multiple packages provide the same executable, `uv` can leave broken symlinks after uninstalling. The `--force` flag ensures clean symlinks.

### Step 4: Verify Installation

```bash
uv tool list | grep notebooklm
```

You should see only:
```
notebooklm-mcp-cli v0.2.0
- nlm
- notebooklm-mcp
```

### Step 5: Re-authenticate

Your existing cookies should still work, but if you encounter auth issues:

```bash
nlm login
```

> **Note:** MCP server configuration (in Claude Code, Cursor, etc.) does not need to change — the executable name `notebooklm-mcp` is the same.

## Uninstalling

To completely remove the MCP:

```bash
# Using uv
uv tool uninstall notebooklm-mcp-cli

# Using pip
pip uninstall notebooklm-mcp-cli

# Using pipx
pipx uninstall notebooklm-mcp-cli

# Remove cached auth tokens and data (optional)
rm -rf ~/.notebooklm-mcp-cli
```

Also remove from your AI tools:

```bash
nlm setup remove claude-code
nlm setup remove cursor
# ... or any configured tool
```

## Authentication

Before using the CLI or MCP, you need to authenticate with NotebookLM:

### CLI Authentication (Recommended)

```bash
# Auto mode: launches your browser, you log in, cookies extracted automatically
nlm login

# Check if already authenticated
nlm login --check

# Use a named profile (for multiple Google accounts)
nlm login --profile work
nlm login --profile personal

# Manual mode: import cookies from a file
nlm login --manual --file cookies.txt

# External CDP provider (e.g., OpenClaw-managed browser)
nlm login --provider openclaw --cdp-url http://127.0.0.1:18800
```

**Profile management:**
```bash
nlm login --check                    # Show current auth status
nlm login switch <profile>           # Switch the default profile
nlm login profile list               # List all profiles with email addresses
nlm login profile delete <profile>   # Delete a profile
nlm login profile rename <old> <new> # Rename a profile
```

Each profile gets its own isolated browser session, so you can be logged into multiple Google accounts simultaneously.

### Standalone Auth Tool

If you only need the MCP server (not the CLI):

```bash
nlm login              # Auto mode (launches browser)
nlm login --manual     # Manual file mode
```

**How it works:** Auto mode launches a dedicated browser profile (supports Chrome, Arc, Brave, Edge, Chromium, and more), you log in to Google, and cookies are extracted automatically. Your login persists for future auth refreshes.

**Prefer a specific browser?** Set it with `nlm config set auth.browser chromium` (or `brave`, `arc`, `edge`, `chrome`, etc.). Falls back to auto-detection if the preferred browser is not found.

For detailed instructions and troubleshooting, see **[docs/AUTHENTICATION.md](docs/AUTHENTICATION.md)**.

## MCP Configuration

> **⚠️ Context Window Warning:** This MCP provides **35 tools**. Disable it when not using NotebookLM to preserve context. In Claude Code: `@notebooklm-mcp` to toggle.

### Automatic Setup (Recommended)

Use `nlm setup` to automatically configure the MCP server for your AI tools — no manual JSON editing required:

```bash
# Add to any supported tool
nlm setup add claude-code
nlm setup add claude-desktop
nlm setup add gemini
nlm setup add github-copilot
nlm setup add cursor
nlm setup add windsurf

# Generate JSON config for any other tool
nlm setup add json

# Check which tools are configured
nlm setup list

# Diagnose installation & auth issues
nlm doctor
```

### Install AI Skills (Optional)

Install the NotebookLM expert guide for your AI assistant to help it use the tools effectively. Supported for **Cline**, **Antigravity**, **OpenClaw**, **Codex**, **OpenCode**, **Claude Code**, and **Gemini CLI**.

```bash
# Install skill files
nlm skill install cline
nlm skill install openclaw
nlm skill install codex
nlm skill install antigravity

# Update skills
nlm skill update
```

### Remove from a tool

```bash
nlm setup remove claude-code
```

### Using uvx (No Install Required)

If you don't want to install the package, you can use `uvx` to run on-the-fly:

```bash
# Run CLI commands directly
uvx --from notebooklm-mcp-cli nlm setup add cursor
uvx --from notebooklm-mcp-cli nlm login
```

For tools that use JSON config, point them to uvx:
```json
{
  "mcpServers": {
    "notebooklm-mcp": {
      "command": "uvx",
      "args": ["--from", "notebooklm-mcp-cli", "notebooklm-mcp"]
    }
  }
}
```

<details>
<summary>Manual Setup (if you prefer)</summary>

> **Tip:** Run `nlm setup add json` for an interactive wizard that generates the right JSON snippet for your tool.

**Claude Code / Gemini CLI** support adding MCP servers via their own CLI:
```bash
claude mcp add --scope user notebooklm-mcp notebooklm-mcp
gemini mcp add --scope user notebooklm-mcp notebooklm-mcp
```

**Cursor / Windsurf** resolve commands from your `PATH`, so the command name is enough:
```json
{
  "mcpServers": {
    "notebooklm-mcp": {
      "command": "notebooklm-mcp"
    }
  }
}
```

| Tool | Config Location |
|------|-----------------|
| Cursor | `~/.cursor/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |

**GitHub Copilot (VS Code workspace)** uses `.vscode/mcp.json` with a top-level `servers` key:
```json
{
  "servers": {
    "notebooklm-mcp": {
      "command": "notebooklm-mcp",
      "args": []
    }
  }
}
```

**Claude Desktop** may not resolve `PATH` — use the full path to the binary:
```json
{
  "mcpServers": {
    "notebooklm-mcp": {
      "command": "/full/path/to/notebooklm-mcp"
    }
  }
}
```

Find your path with: `which notebooklm-mcp`

| Tool | Config Location |
|------|-----------------|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| GitHub Copilot | `.vscode/mcp.json` |

</details>

📚 **Full configuration details:** [MCP Guide](docs/MCP_GUIDE.md) — Server options, environment variables, HTTP transport, multi-user setup, and context window management.

## What You Can Do

Simply chat with your AI tool (Claude Code, Cursor, Gemini CLI) using natural language. Here are some examples:

### Research & Discovery

- "List all my NotebookLM notebooks"
- "Create a new notebook called 'AI Strategy Research'"
- "Start web research on 'enterprise AI ROI metrics' and show me what sources it finds"
- "Do a deep research on 'cloud marketplace trends' and import the top 10 sources"
- "Search my Google Drive for documents about 'product roadmap' and create a notebook"

### Adding Content

- "Add this URL to my notebook: https://example.com/article"
- "Add this YouTube video about Kubernetes to the notebook"
- "Add my meeting notes as a text source to this notebook"
- "Import this Google Doc into my research notebook"

### AI-Powered Analysis

- "What are the key findings in this notebook?"
- "Summarize the main arguments across all these sources"
- "What does this source say about security best practices?"
- "Get an AI summary of what this notebook is about"
- "Configure the chat to use a learning guide style with longer responses"

*(All queries sent from CLI or MCP automatically persist in your NotebookLM web UI chat history!)*

### Content Generation

- "Create an audio podcast overview of this notebook in deep dive format"
- "Generate a video explainer with classic visual style"
- "Make a briefing doc from these sources"
- "Create flashcards for studying, medium difficulty"
- "Generate an infographic in landscape orientation with professional style"
- "Build a mind map from my research sources"
- "Create a slide deck presentation from this notebook"

### Smart Management

- "Check which Google Drive sources are out of date and sync them"
- "Show me all the sources in this notebook with their freshness status"
- "Delete this source from the notebook"
- "Check the status of my audio overview generation"

### Sharing & Collaboration

- "Show me the sharing settings for this notebook"
- "Make this notebook public so anyone with the link can view it"
- "Disable public access to this notebook"
- "Invite user@example.com as an editor to this notebook"
- "Add a viewer to my research notebook"

**Pro tip:** After creating studio content (audio, video, reports, etc.), poll the status to get download URLs when generation completes.

## Authentication Lifecycle

| Component | Duration | Refresh |
|-----------|----------|---------|
| Cookies | ~2-4 weeks | Auto-refresh via headless browser (if profile saved) |
| CSRF Token | ~minutes | Auto-refreshed on every request failure |
| Session ID | Per MCP session | Auto-extracted on MCP start |

**v0.1.9+**: The server now automatically handles token expiration:
1. Refreshes CSRF tokens immediately when expired
2. Reloads cookies from disk if updated externally
3. Runs headless browser auth if profile has saved login

You can also call `refresh_auth()` to explicitly reload tokens.

If automatic refresh fails (Google login fully expired), run `nlm login` again.

## Troubleshooting

### `uv tool upgrade` Not Installing Latest Version

**Symptoms:**
- Running `uv tool upgrade notebooklm-mcp-cli` installs an older version (e.g., 0.1.5 instead of 0.1.9)
- `uv cache clean` doesn't fix the issue

**Why this happens:** `uv tool upgrade` respects version constraints from your original installation. If you initially installed an older version or with a constraint, `upgrade` stays within those bounds by design.

**Fix — Force reinstall:**
```bash
uv tool install --force notebooklm-mcp-cli
```

This bypasses any cached constraints and installs the absolute latest version from PyPI.

**Verify:**
```bash
uv tool list | grep notebooklm
# Should show: notebooklm-mcp-cli v0.1.9 (or latest)
```


## Limitations

- **Rate limits**: Free tier has ~50 queries/day
- **No official support**: API may change without notice
- **Cookie expiration**: Need to re-extract cookies every few weeks

## Contributing

See [CLAUDE.md](CLAUDE.md) for detailed API documentation and how to add new features.

## Vibe Coding Alert

Full transparency: this project was built by a non-developer using AI coding assistants. If you're an experienced Python developer, you might look at this codebase and wince. That's okay.

The goal here was to scratch an itch - programmatic access to NotebookLM - and learn along the way. The code works, but it's likely missing patterns, optimizations, or elegance that only years of experience can provide.

**This is where you come in.** If you see something that makes you cringe, please consider contributing rather than just closing the tab. This is open source specifically because human expertise is irreplaceable. Whether it's refactoring, better error handling, type hints, or architectural guidance - PRs and issues are welcome.

Think of it as a chance to mentor an AI-assisted developer through code review. We all benefit when experienced developers share their knowledge.

## Credits

Special thanks to:
- **Le Anh Tuan** ([@latuannetnam](https://github.com/latuannetnam)) for contributing the HTTP transport, debug logging system, and performance optimizations.
- **David Szabo-Pele** ([@davidszp](https://github.com/davidszp)) for the `source_get_content` tool and Linux auth fixes.
- **saitrogen** ([@saitrogen](https://github.com/saitrogen)) for the research polling query fallback fix.
- **devnull03** ([@devnull03](https://github.com/devnull03)) for multi-browser CDP authentication support (Arc, Brave, Edge, Chromium, Vivaldi, Opera).
- **VooDisss** ([@VooDisss](https://github.com/VooDisss)) for multi-browser authentication improvements.
- **codepiano** ([@codepiano](https://github.com/codepiano)) for the configurable DevTools timeout for the auth CLI.
- **Tony Hansmann** ([@997unix](https://github.com/997unix)) for contributing the `nlm setup` and `nlm doctor` commands and CLI Guide documentation.
- **Fabiana Furtado** ([@fabianafurtadoff](https://github.com/fabianafurtadoff)) for batch operations, cross-notebook query, pipelines, and smart select/tagging (PR #90).


## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=jacob-bd/notebooklm-mcp-cli&type=Date)](https://star-history.com/#jacob-bd/notebooklm-mcp-cli&Date)

## License

[MIT License](LICENSE)
